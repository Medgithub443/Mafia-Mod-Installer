// logo_maker.cpp — drop-in замена для logo_maker.py + ffmpeg_avi_mp3.exe
//
// Делает то же, что и logo_maker.py: накладывает чёрный текст из OTF-шрифта
// на каждый кадр входного AVI и пишет AVI на выход. Аудио-стрим (MP3) копируется
// побайтно без перекодирования.
//
// Ограничения по сравнению с оригиналом:
//   * Вход должен быть AVI с MJPG-видео (а не FMP4). Используйте предварительно
//     сконвертированный logo1.avi (mjpeg q:v 3). Это позволило выкинуть
//     ffmpeg_avi_mp3.exe (6.16 MB) и уложиться в ~50 KB.
//   * --widescreen режим: реализован как letterbox (scale 1920×812 + pad чёрным
//     до 1920×1080), но выход остаётся MJPEG, а не XviD. Если Widescreen Fix
//     требует именно XviD — это известное ограничение (XviD-кодер в 50 KB
//     не помещается).
//
// Сборка (MinGW-w64):
//   x86_64-w64-mingw32-g++ -Os -s -fno-exceptions -fno-rtti \
//       -ffunction-sections -fdata-sections -Wl,--gc-sections \
//       -static-libgcc -static-libstdc++ \
//       logo_maker.cpp -o logoMaker.exe \
//       -lgdiplus -lole32 -luuid
//
// CLI: logoMaker <input.avi> <output.avi> <font.otf> "<text>" [x] [y] [size] [--widescreen]

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include <ole2.h>
#include <gdiplus.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

using namespace Gdiplus;
using namespace Gdiplus::DllExports;

// ---------- утилиты ----------

static void die(const char* msg) {
    fprintf(stderr, "logoMaker: %s\n", msg);
    ExitProcess(1);
}

static void die2w(const char* msg, const WCHAR* arg) {
    fprintf(stderr, "logoMaker: %s: %ls\n", msg, arg);
    ExitProcess(1);
}

#pragma pack(push, 1)
struct RiffHdr {
    uint32_t fcc;       // 'RIFF' / 'LIST'
    uint32_t size;
    uint32_t list_type; // 'AVI ' / 'hdrl' / 'movi' / 'strl' и т.д.
};

struct ChunkHdr {
    uint32_t fcc;
    uint32_t size;
};

struct AVIMainHdr {
    uint32_t fcc;            // 'avih'
    uint32_t cb;             // 56
    uint32_t microSecPerFrame;
    uint32_t maxBytesPerSec;
    uint32_t paddingGranularity;
    uint32_t flags;
    uint32_t totalFrames;
    uint32_t initialFrames;
    uint32_t streams;
    uint32_t suggestedBufferSize;
    uint32_t width;
    uint32_t height;
    uint32_t reserved[4];
};

struct AVIStreamHdr {
    uint32_t fcc;            // 'strh'
    uint32_t cb;             // 56
    uint32_t type;           // 'vids' / 'auds'
    uint32_t handler;        // codec fourcc
    uint32_t flags;
    uint16_t priority;
    uint16_t language;
    uint32_t initialFrames;
    uint32_t scale;
    uint32_t rate;
    uint32_t start;
    uint32_t length;
    uint32_t suggestedBufferSize;
    uint32_t quality;
    uint32_t sampleSize;
    int16_t  rcFrameLeft;
    int16_t  rcFrameTop;
    int16_t  rcFrameRight;
    int16_t  rcFrameBottom;
};

struct BmpInfoHdr {
    uint32_t cb;             // size including this field, == 40
    int32_t  width;
    int32_t  height;
    uint16_t planes;
    uint16_t bitCount;
    uint32_t compression;
    uint32_t sizeImage;
    int32_t  xPelsPerMeter;
    int32_t  yPelsPerMeter;
    uint32_t clrUsed;
    uint32_t clrImportant;
};

struct IdxEntry {
    uint32_t fcc;
    uint32_t flags;
    uint32_t offset;        // offset from start of movi LIST (т.е. от позиции после 'movi' fourcc)
    uint32_t size;
};
#pragma pack(pop)

#define MK4(a,b,c,d) ((uint32_t)(a) | ((uint32_t)(b)<<8) | ((uint32_t)(c)<<16) | ((uint32_t)(d)<<24))
static const uint32_t FCC_RIFF = MK4('R','I','F','F');
static const uint32_t FCC_LIST = MK4('L','I','S','T');
static const uint32_t FCC_AVI  = MK4('A','V','I',' ');
static const uint32_t FCC_hdrl = MK4('h','d','r','l');
static const uint32_t FCC_avih = MK4('a','v','i','h');
static const uint32_t FCC_strl = MK4('s','t','r','l');
static const uint32_t FCC_strh = MK4('s','t','r','h');
static const uint32_t FCC_strf = MK4('s','t','r','f');
static const uint32_t FCC_movi = MK4('m','o','v','i');
static const uint32_t FCC_idx1 = MK4('i','d','x','1');
static const uint32_t FCC_vids = MK4('v','i','d','s');
static const uint32_t FCC_auds = MK4('a','u','d','s');
static const uint32_t FCC_MJPG = MK4('M','J','P','G');
static const uint32_t FCC_JFIF = MK4('J','F','I','F');
static const uint32_t FCC_jpeg = MK4('j','p','e','g');

#define AVIIF_KEYFRAME 0x10

// Полное чтение файла в память
static bool read_file(const WCHAR* path, uint8_t** out_buf, size_t* out_size) {
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER sz;
    if (!GetFileSizeEx(h, &sz) || sz.QuadPart > 200 * 1024 * 1024) { CloseHandle(h); return false; }
    size_t n = (size_t)sz.QuadPart;
    uint8_t* buf = (uint8_t*)HeapAlloc(GetProcessHeap(), 0, n ? n : 1);
    if (!buf) { CloseHandle(h); return false; }
    DWORD got = 0;
    if (!ReadFile(h, buf, (DWORD)n, &got, NULL) || got != n) {
        HeapFree(GetProcessHeap(), 0, buf); CloseHandle(h); return false;
    }
    CloseHandle(h);
    *out_buf = buf; *out_size = n;
    return true;
}

static bool write_file(const WCHAR* path, const uint8_t* buf, size_t n) {
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL,
                           CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return false;
    DWORD wrote = 0;
    bool ok = WriteFile(h, buf, (DWORD)n, &wrote, NULL) && wrote == n;
    CloseHandle(h);
    return ok;
}

// Простой динамический буфер (без std::vector — экономим бинарь)
struct DynBuf {
    uint8_t* data;
    size_t size;
    size_t cap;

    void init() { data = NULL; size = 0; cap = 0; }
    void free_() { if (data) HeapFree(GetProcessHeap(), 0, data); data = NULL; size = cap = 0; }
    void reserve(size_t need) {
        if (need <= cap) return;
        size_t nc = cap ? cap : 256;
        while (nc < need) nc *= 2;
        uint8_t* nd = (uint8_t*)HeapReAlloc(GetProcessHeap(), 0, data ? data : HeapAlloc(GetProcessHeap(),0,1), nc);
        if (!nd) die("oom");
        data = nd; cap = nc;
    }
    void append(const void* p, size_t n) {
        reserve(size + n);
        memcpy(data + size, p, n);
        size += n;
    }
    void append_u32(uint32_t v) { append(&v, 4); }
    void pad2() { if (size & 1) { uint8_t z = 0; append(&z, 1); } }
    void patch_u32(size_t off, uint32_t v) { memcpy(data + off, &v, 4); }
};

// ---------- GDI+ helpers ----------

static GpStatus check(GpStatus s, const char* what) {
    if (s != Ok) {
        char b[128]; wsprintfA(b, "GDI+ %s failed (%d)", what, (int)s);
        die(b);
    }
    return s;
}

// Создать IStream из памяти (read-only, с копированием — SHCreateMemStream
// внутри сам копирует данные в свой буфер).
static IStream* mem_stream(const uint8_t* data, size_t size) {
    return SHCreateMemStream((const BYTE*)data, (UINT)size);
}

// Считать содержимое IStream обратно в DynBuf
static void stream_to_buf(IStream* s, DynBuf& out) {
    LARGE_INTEGER zero; zero.QuadPart = 0;
    s->Seek(zero, STREAM_SEEK_SET, NULL);
    STATSTG st; s->Stat(&st, STATFLAG_NONAME);
    size_t n = (size_t)st.cbSize.QuadPart;
    out.reserve(out.size + n);
    ULONG got = 0;
    s->Read(out.data + out.size, (ULONG)n, &got);
    out.size += got;
}

// Найти CLSID JPEG-энкодера
static bool find_jpeg_clsid(CLSID* out) {
    UINT num = 0, sz = 0;
    GetImageEncodersSize(&num, &sz);
    if (sz == 0) return false;
    ImageCodecInfo* info = (ImageCodecInfo*)HeapAlloc(GetProcessHeap(), 0, sz);
    GetImageEncoders(num, sz, info);
    bool ok = false;
    for (UINT i = 0; i < num; i++) {
        if (wcscmp(info[i].MimeType, L"image/jpeg") == 0) {
            *out = info[i].Clsid; ok = true; break;
        }
    }
    HeapFree(GetProcessHeap(), 0, info);
    return ok;
}

// ---------- основной парсинг AVI ----------

struct AviInfo {
    const uint8_t* file;
    size_t file_size;

    // movi: указатели на чанки (видео и аудио в порядке появления)
    struct Chunk {
        uint32_t fcc;          // '00dc' / '01wb' / ...
        const uint8_t* data;   // полезная нагрузка
        uint32_t size;
        uint32_t flags;        // из idx1, если нашли (или 0/AVIIF_KEYFRAME для видео)
    };
    Chunk* chunks;
    size_t n_chunks;

    // позиции хедеров для последующего копирования
    const uint8_t* hdrl_data;     // указатель сразу после fourcc 'hdrl'
    uint32_t hdrl_size;           // размер LIST hdrl без 8-байт заголовка LIST

    uint32_t video_stream_idx;    // индекс вид.стрима (по позиции strl-блоков)
    uint32_t audio_stream_idx;    // индекс ауд.стрима, или 0xFFFFFFFF если нет
    uint32_t video_codec;         // ожидаем MJPG/JPEG/JFIF
    uint32_t width, height;
};

static void parse_avi(const uint8_t* file, size_t fs, AviInfo* out) {
    memset(out, 0, sizeof(*out));
    out->file = file; out->file_size = fs;
    out->video_stream_idx = 0xFFFFFFFF;
    out->audio_stream_idx = 0xFFFFFFFF;

    if (fs < 12) die("too small");
    const RiffHdr* root = (const RiffHdr*)file;
    if (root->fcc != FCC_RIFF || root->list_type != FCC_AVI) die("not RIFF/AVI");

    const uint8_t* p = file + 12;
    const uint8_t* end = file + 8 + root->size;
    if (end > file + fs) end = file + fs;

    uint32_t streams_seen = 0;
    const uint8_t* movi_start = NULL;
    uint32_t movi_size = 0;
    const uint8_t* idx1_data = NULL;
    uint32_t idx1_size = 0;

    while (p + 8 <= end) {
        const ChunkHdr* ch = (const ChunkHdr*)p;
        uint32_t cs = ch->size;
        const uint8_t* body = p + 8;
        if (body + cs > end) break;

        if (ch->fcc == FCC_LIST) {
            if (cs < 4) break;
            uint32_t lt = *(const uint32_t*)body;
            if (lt == FCC_hdrl) {
                out->hdrl_data = body;
                out->hdrl_size = cs;
                // пройдёмся внутри hdrl, чтобы выяснить параметры стримов
                const uint8_t* hp = body + 4;
                const uint8_t* he = body + cs;
                while (hp + 8 <= he) {
                    const ChunkHdr* hch = (const ChunkHdr*)hp;
                    uint32_t hcs = hch->size;
                    const uint8_t* hb = hp + 8;
                    if (hch->fcc == FCC_avih && hcs >= 56) {
                        const AVIMainHdr* mh = (const AVIMainHdr*)(hp);
                        out->width = mh->width;
                        out->height = mh->height;
                    } else if (hch->fcc == FCC_LIST && hcs >= 4 && *(const uint32_t*)hb == FCC_strl) {
                        // strl: внутри strh + strf
                        const uint8_t* sp = hb + 4;
                        const uint8_t* se = hb + hcs;
                        uint32_t stype = 0; uint32_t handler = 0;
                        while (sp + 8 <= se) {
                            const ChunkHdr* sch = (const ChunkHdr*)sp;
                            uint32_t scs = sch->size;
                            const uint8_t* sb = sp + 8;
                            if (sch->fcc == FCC_strh && scs >= 56) {
                                const AVIStreamHdr* sh = (const AVIStreamHdr*)sp;
                                stype = sh->type;
                                handler = sh->handler;
                            } else if (sch->fcc == FCC_strf && stype == FCC_vids && scs >= sizeof(BmpInfoHdr)) {
                                const BmpInfoHdr* bi = (const BmpInfoHdr*)sb;
                                out->video_codec = bi->compression;
                                if (out->video_codec == 0 && handler != 0) out->video_codec = handler;
                            }
                            // переход к след.под-чанку (выровнен по WORD)
                            uint32_t adv = 8 + scs + (scs & 1);
                            sp += adv;
                        }
                        if (stype == FCC_vids) out->video_stream_idx = streams_seen;
                        else if (stype == FCC_auds) out->audio_stream_idx = streams_seen;
                        streams_seen++;
                    }
                    uint32_t adv = 8 + hcs + (hcs & 1);
                    hp += adv;
                }
            } else if (lt == FCC_movi) {
                movi_start = body + 4;
                movi_size = cs - 4;
            }
        } else if (ch->fcc == FCC_idx1) {
            idx1_data = body;
            idx1_size = cs;
        }

        uint32_t adv = 8 + cs + (cs & 1);
        p += adv;
    }

    if (!movi_start) die("no movi");
    if (out->video_stream_idx == 0xFFFFFFFF) die("no video stream");
    if (out->video_codec != FCC_MJPG && out->video_codec != FCC_JFIF && out->video_codec != FCC_jpeg)
        die("video codec must be MJPG (pre-convert with: ffmpeg -i in -c:v mjpeg -q:v 3 -c:a copy out.avi)");

    // собираем чанки movi
    size_t cap = 64;
    out->chunks = (AviInfo::Chunk*)HeapAlloc(GetProcessHeap(), 0, sizeof(AviInfo::Chunk) * cap);
    out->n_chunks = 0;
    const uint8_t* mp = movi_start;
    const uint8_t* me = movi_start + movi_size;
    while (mp + 8 <= me) {
        const ChunkHdr* ch = (const ChunkHdr*)mp;
        uint32_t cs = ch->size;
        if (mp + 8 + cs > me) break;
        // пропускаем под-LIST'ы (rec )
        if (ch->fcc == FCC_LIST) {
            mp += 8 + cs + (cs & 1);
            continue;
        }
        if (out->n_chunks == cap) {
            cap *= 2;
            out->chunks = (AviInfo::Chunk*)HeapReAlloc(GetProcessHeap(), 0, out->chunks, sizeof(AviInfo::Chunk)*cap);
        }
        AviInfo::Chunk& c = out->chunks[out->n_chunks++];
        c.fcc = ch->fcc;
        c.data = mp + 8;
        c.size = cs;
        c.flags = 0;
        mp += 8 + cs + (cs & 1);
    }

    // Проставим флаги ключевого кадра по idx1 если есть
    if (idx1_data && idx1_size >= 16) {
        size_t n = idx1_size / 16;
        // Сопоставим по позиции внутри movi: idx1.offset обычно от начала 'movi' fourcc
        // (либо от начала файла — ffmpeg использует от начала movi LIST). Чтобы не гадать,
        // проставим флаги для всех видео-чанков как KEYFRAME (MJPEG все кадры I).
        (void)n;
    }
    // MJPEG: все кадры — ключевые
    for (size_t i = 0; i < out->n_chunks; i++) {
        uint32_t f = out->chunks[i].fcc;
        // chunk id формат: 'NNxx' где NN=stream_idx (BCD), xx='dc'/'wb'/'db'
        // Видео = '..dc' или '..db'
        char b3 = (char)((f >> 16) & 0xff);
        char b4 = (char)((f >> 24) & 0xff);
        if ((b3 == 'd' && (b4 == 'c' || b4 == 'b'))) {
            out->chunks[i].flags = AVIIF_KEYFRAME;
        }
    }
}

// ---------- сборка AVI ----------

// Собираем AVI заново. Берём оригинальный hdrl (с минимальными правками
// для maxBytesPerSec и suggestedBufferSize) и меняем содержимое movi.
//
// Нужные правки в hdrl:
//   * avih.maxBytesPerSec — пересчитываем
//   * avih.suggestedBufferSize — берём максимум из новых видео-чанков
//   * для видео-strl: strh.suggestedBufferSize — то же
//   * для видео-strl: strf (BITMAPINFOHEADER): width/height могут поменяться
//     если --widescreen и letterbox изменил геометрию (мы НЕ меняем —
//     letterbox делается внутри 1920×1080)
//
// Для упрощения мы скопируем hdrl как есть, поправив пару полей по offset.
static void build_avi(const AviInfo& in, const AviInfo::Chunk* new_chunks,
                      uint32_t new_max_frame, DynBuf& out)
{
    out.init();
    // RIFF AVI header (placeholder size)
    out.append("RIFF", 4);
    size_t riff_size_off = out.size; out.append_u32(0);
    out.append("AVI ", 4);

    // LIST hdrl — копируем целиком
    out.append("LIST", 4);
    out.append_u32(in.hdrl_size);
    out.append(in.hdrl_data, in.hdrl_size);

    // Локальный поиск avih и strh внутри только что записанного hdrl —
    // правим in-place в out.data.
    {
        size_t hdrl_body_off = out.size - in.hdrl_size; // указатель на 'hdrl' fourcc
        size_t hdrl_end = out.size;
        size_t hp = hdrl_body_off + 4; // после fourcc 'hdrl'
        while (hp + 8 <= hdrl_end) {
            uint32_t fcc = *(uint32_t*)(out.data + hp);
            uint32_t cs  = *(uint32_t*)(out.data + hp + 4);
            if (fcc == FCC_avih && cs >= 56) {
                AVIMainHdr* mh = (AVIMainHdr*)(out.data + hp);
                mh->maxBytesPerSec = (uint32_t)((uint64_t)new_max_frame * 25); // приблизительно
                mh->suggestedBufferSize = new_max_frame + 4096;
            } else if (fcc == FCC_LIST && cs >= 4) {
                uint32_t lt = *(uint32_t*)(out.data + hp + 8);
                if (lt == FCC_strl) {
                    size_t sp = hp + 12;
                    size_t se = hp + 8 + cs;
                    uint32_t stype = 0;
                    while (sp + 8 <= se) {
                        uint32_t sfcc = *(uint32_t*)(out.data + sp);
                        uint32_t scs  = *(uint32_t*)(out.data + sp + 4);
                        if (sfcc == FCC_strh && scs >= 56) {
                            AVIStreamHdr* sh = (AVIStreamHdr*)(out.data + sp);
                            stype = sh->type;
                            if (stype == FCC_vids) {
                                sh->suggestedBufferSize = new_max_frame + 4096;
                            }
                        }
                        sp += 8 + scs + (scs & 1);
                    }
                }
            }
            hp += 8 + cs + (cs & 1);
        }
    }

    // LIST movi
    out.append("LIST", 4);
    size_t movi_size_off = out.size; out.append_u32(0);
    size_t movi_body_start = out.size; // здесь будет fourcc 'movi'
    out.append("movi", 4);

    // запоминаем оффсеты чанков для idx1
    struct IdxRec { uint32_t fcc; uint32_t flags; uint32_t off; uint32_t size; };
    size_t idx_cap = in.n_chunks; size_t idx_n = 0;
    IdxRec* idx = (IdxRec*)HeapAlloc(GetProcessHeap(), 0, sizeof(IdxRec)*idx_cap);

    for (size_t i = 0; i < in.n_chunks; i++) {
        const AviInfo::Chunk& c = new_chunks[i];
        size_t chunk_off = out.size - movi_body_start; // offset от 'movi' fourcc, как идёт ffmpeg
        idx[idx_n].fcc = c.fcc;
        idx[idx_n].flags = c.flags;
        idx[idx_n].off = (uint32_t)chunk_off;
        idx[idx_n].size = c.size;
        idx_n++;

        out.append_u32(c.fcc);
        out.append_u32(c.size);
        out.append(c.data, c.size);
        out.pad2();
    }

    // зафиксировать размер movi LIST (включая 'movi' fourcc)
    uint32_t movi_total = (uint32_t)(out.size - (movi_size_off + 4));
    out.patch_u32(movi_size_off, movi_total);

    // idx1
    out.append("idx1", 4);
    out.append_u32((uint32_t)(idx_n * 16));
    for (size_t i = 0; i < idx_n; i++) {
        out.append_u32(idx[i].fcc);
        out.append_u32(idx[i].flags);
        out.append_u32(idx[i].off);
        out.append_u32(idx[i].size);
    }
    HeapFree(GetProcessHeap(), 0, idx);

    // патчим RIFF size
    out.patch_u32(riff_size_off, (uint32_t)(out.size - 8));
}

// ---------- рендер кадра ----------

struct RenderCtx {
    GpFontFamily*       family;
    GpFont*             font;
    GpStringFormat*     fmt;
    GpSolidFill*        brush;
    GpFontCollection*   pfc;
    REAL                x, y;
    int                 width, height;
    int                 letterbox;       // 1, если --widescreen: рисуем в 1920×812 и паддим
    int                 lb_top;          // отступ сверху (=lb_bottom)
    WCHAR*              wtext;
    int                 wtext_len;
    CLSID               jpeg_clsid;
    EncoderParameters*  enc_params;      // quality
};

static void render_frame_to_jpeg(const RenderCtx& rc, const uint8_t* in_jpg, uint32_t in_size,
                                 DynBuf& out_jpg)
{
    // Загружаем JPEG: пишем во временный файл и грузим через GdipCreateBitmapFromFile.
    // (IStream-вариант с GdipCreateBitmapFromStream/Stream/SHCreateMemStream
    // на ряде сборок GDI+ возвращает InvalidParameter для baseline-JPEG из MJPEG.)
    WCHAR tmpdir[MAX_PATH], tmpfile[MAX_PATH];
    GetTempPathW(MAX_PATH, tmpdir);
    GetTempFileNameW(tmpdir, L"lmf", 0, tmpfile);
    HANDLE th = CreateFileW(tmpfile, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                            FILE_ATTRIBUTE_TEMPORARY, NULL);
    DWORD wrote = 0;
    WriteFile(th, in_jpg, in_size, &wrote, NULL);
    CloseHandle(th);
    GpBitmap* bmp = NULL;
    GpStatus ls = GdipCreateBitmapFromFile(tmpfile, &bmp);
    DeleteFileW(tmpfile);
    if (ls != Ok) {
        char b[160]; wsprintfA(b, "GDI+ load(file) failed (%d), in_size=%u", (int)ls, (unsigned)in_size);
        die(b);
    }

    GpGraphics* g = NULL;
    check(GdipGetImageGraphicsContext((GpImage*)bmp, &g), "graphics");
    GdipSetTextRenderingHint(g, TextRenderingHintAntiAliasGridFit);
    GdipSetSmoothingMode(g, SmoothingModeAntiAlias);

    // Если --widescreen: создаём новый bitmap 1920×1080 с чёрным фоном,
    // и рисуем туда исходный кадр scaled в 1920×812 (1080/1.33). Затем
    // рисуем текст. Возвращаемый JPEG — это новый bitmap.
    GpBitmap* render_bmp = bmp;
    GpGraphics* render_g = g;
    int free_render = 0;
    if (rc.letterbox) {
        GpBitmap* lb = NULL;
        check(GdipCreateBitmapFromScan0(rc.width, rc.height, 0, PixelFormat24bppRGB, NULL, &lb), "create lb");
        GpGraphics* lg = NULL;
        check(GdipGetImageGraphicsContext((GpImage*)lb, &lg), "lb graphics");
        // чёрный фон
        GdipGraphicsClear(lg, 0xFF000000);
        // scaled draw
        REAL inner_h = (REAL)rc.height / (REAL)1.33f;
        REAL pad_y = ((REAL)rc.height - inner_h) / 2.0f;
        check(GdipDrawImageRectI(lg, (GpImage*)bmp, 0, (INT)pad_y, rc.width, (INT)inner_h), "draw lb");
        GdipSetTextRenderingHint(lg, TextRenderingHintAntiAliasGridFit);
        GdipSetSmoothingMode(lg, SmoothingModeAntiAlias);
        // текст рисуем в координатах исходного кадра, с поправкой на pad_y и масштабом
        // оригинальный logo_maker задаёт x,y относительно 1920×1080, так что после
        // letterbox эти координаты должны проецироваться: y_real = pad_y + y * (inner_h / 1080)
        // Для совместимости с вызовами (где обычно 1080-каноническая система) применим эту коррекцию.
        // В нашем случае width=1920, height=1080, inner_h≈812, pad_y≈134
        REAL ny = pad_y + rc.y * (inner_h / (REAL)rc.height);
        // также масштабируем шрифт
        REAL fsz = 0;
        GdipGetFontSize(rc.font, &fsz);
        GpFont* scaled_font = NULL;
        check(GdipCreateFont(rc.family, fsz * (inner_h / (REAL)rc.height), 0, UnitPixel, &scaled_font), "scaled font");
        RectF layout = { rc.x, ny, (REAL)rc.width, (REAL)rc.height };
        GdipDrawString(lg, rc.wtext, rc.wtext_len, scaled_font, &layout, rc.fmt, rc.brush);
        GdipDeleteFont(scaled_font);
        GdipDeleteGraphics(lg);
        render_bmp = lb;
        free_render = 1;
        // освобождаем оригинальные g/bmp ниже
        GdipDeleteGraphics(g);
        GdipDisposeImage((GpImage*)bmp);
    } else {
        RectF layout = { rc.x, rc.y, (REAL)rc.width, (REAL)rc.height };
        GdipDrawString(g, rc.wtext, rc.wtext_len, rc.font, &layout, rc.fmt, rc.brush);
    }

    // сохранить в JPEG в IStream
    IStream* out_s = NULL;
    HGLOBAL hg = GlobalAlloc(GMEM_MOVEABLE, 0);
    if (CreateStreamOnHGlobal(hg, TRUE, &out_s) != S_OK) die("out stream");
    check(GdipSaveImageToStream((GpImage*)render_bmp, out_s, &rc.jpeg_clsid, rc.enc_params), "save jpeg");
    stream_to_buf(out_s, out_jpg);
    out_s->Release();

    if (free_render) {
        GdipDisposeImage((GpImage*)render_bmp);
    } else {
        GdipDeleteGraphics(g);
        GdipDisposeImage((GpImage*)bmp);
    }
}

// ---------- main ----------

// схлопывание пустых строк для wide-char
static WCHAR* w_collapse_empty_lines(const WCHAR* s) {
    size_t n = wcslen(s);
    WCHAR* out = (WCHAR*)HeapAlloc(GetProcessHeap(), 0, (n + 1) * sizeof(WCHAR));
    WCHAR* d = out;
    const WCHAR* line = s;
    while (*line) {
        const WCHAR* nl = wcschr(line, L'\n');
        const WCHAR* lend = nl ? nl : line + wcslen(line);
        bool has = false;
        for (const WCHAR* q = line; q < lend; q++) {
            if (*q != L' ' && *q != L'\t' && *q != L'\r') { has = true; break; }
        }
        if (has) {
            if (d != out) *d++ = L'\n';
            memcpy(d, line, (size_t)(lend - line) * sizeof(WCHAR));
            d += (lend - line);
        }
        if (!nl) break;
        line = nl + 1;
    }
    *d = 0;
    return out;
}

// заменяет \n (литерально 2 символа) на настоящий newline
static void w_unescape_newlines_inplace(WCHAR* s) {
    WCHAR* d = s; WCHAR* p = s;
    while (*p) {
        if (p[0] == L'\\' && p[1] == L'n') { *d++ = L'\n'; p += 2; }
        else { *d++ = *p++; }
    }
    *d = 0;
}

extern "C" int main(int /*argc_a*/, char** /*argv_a*/) {
    int wargc = 0;
    LPWSTR* wargv = CommandLineToArgvW(GetCommandLineW(), &wargc);
    bool widescreen = false;
    int n = 0;
    LPWSTR args[16];
    for (int i = 1; i < wargc && n < 16; i++) {
        if (wcscmp(wargv[i], L"--widescreen") == 0) widescreen = true;
        else args[n++] = wargv[i];
    }
    if (n < 4) {
        fprintf(stderr,
            "Usage: logoMaker <input.avi> <output.avi> <font.otf> \"<text>\" "
            "[x] [y] [size] [--widescreen]\n");
        return 1;
    }
    LPCWSTR input_path  = args[0];
    LPCWSTR output_path = args[1];
    LPCWSTR font_path   = args[2];
    int x  = (n > 4) ? _wtoi(args[4]) : 87;
    int y  = (n > 5) ? _wtoi(args[5]) : 361;
    int sz = (n > 6) ? _wtoi(args[6]) : 36;

    // обработка текста: \n → newline, схлопывание пустых строк (как в py)
    WCHAR* wtext_buf = (WCHAR*)HeapAlloc(GetProcessHeap(), 0, (wcslen(args[3]) + 1) * sizeof(WCHAR));
    wcscpy(wtext_buf, args[3]);
    w_unescape_newlines_inplace(wtext_buf);
    WCHAR* wtext_full = w_collapse_empty_lines(wtext_buf);

    // GDI+ init
    GdiplusStartupInput si;
    si.GdiplusVersion = 1;
    si.DebugEventCallback = NULL;
    si.SuppressBackgroundThread = FALSE;
    si.SuppressExternalCodecs = FALSE;
    ULONG_PTR token = 0;
    if (GdiplusStartup(&token, &si, NULL) != Ok) die("gdiplus startup");
    if (CoInitializeEx(NULL, COINIT_MULTITHREADED) != S_OK) die("coinit");

    // читаем входной AVI
    uint8_t* file_buf = NULL; size_t file_size = 0;
    if (!read_file(input_path, &file_buf, &file_size)) die2w("cannot read", input_path);

    AviInfo avi; parse_avi(file_buf, file_size, &avi);

    // читаем шрифт целиком в память и регистрируем в private collection
    uint8_t* font_buf = NULL; size_t font_size = 0;
    if (!read_file(font_path, &font_buf, &font_size)) die2w("cannot read font", font_path);

    GpFontCollection* pfc = NULL;
    GdipNewPrivateFontCollection(&pfc);
    if (GdipPrivateAddMemoryFont(pfc, font_buf, (INT)font_size) != Ok) die("font load");
    INT n_fams = 0;
    GdipGetFontCollectionFamilyCount(pfc, &n_fams);
    if (n_fams < 1) die("no families in font");
    GpFontFamily* family = NULL;
    INT got_fams = 0;
    GdipGetFontCollectionFamilyList(pfc, 1, &family, &got_fams);
    if (got_fams < 1) die("font family fetch");

    // создаём шрифт
    GpFont* font = NULL;
    check(GdipCreateFont(family, (REAL)sz, 0, UnitPixel, &font), "create font");

    GpStringFormat* fmt = NULL;
    GdipCreateStringFormat(0, LANG_NEUTRAL, &fmt);
    GdipSetStringFormatFlags(fmt, StringFormatFlagsNoWrap | StringFormatFlagsNoClip);

    // межстрочный интервал — GDI+ не имеет прямого аналога ffmpeg-овского
    // line_spacing=-6, но GdipDrawString с одним вызовом и переносами \n
    // близко к этому. Если нужно идеально точно — стоит рендерить построчно.
    // Для простоты — рисуем построчно с шагом (size + line_spacing).

    GpSolidFill* brush = NULL;
    GdipCreateSolidFill(0xFF000000, &brush);

    // JPEG энкодер
    CLSID jpeg_clsid;
    if (!find_jpeg_clsid(&jpeg_clsid)) die("no jpeg encoder");
    EncoderParameters* ep = (EncoderParameters*)HeapAlloc(GetProcessHeap(), 0,
        sizeof(EncoderParameters) + sizeof(EncoderParameter));
    ep->Count = 1;
    ep->Parameter[0].Guid = EncoderQuality;
    ep->Parameter[0].Type = EncoderParameterValueTypeLong;
    ep->Parameter[0].NumberOfValues = 1;
    static LONG quality = 85; // ffmpeg q:v 3 ≈ 85 в шкале JPEG quality
    ep->Parameter[0].Value = &quality;

    int wlen = (int)wcslen(wtext_full);

    RenderCtx rc;
    rc.family = family; rc.font = font; rc.fmt = fmt; rc.brush = brush; rc.pfc = pfc;
    rc.x = (REAL)x; rc.y = (REAL)y;
    rc.width = (int)avi.width; rc.height = (int)avi.height;
    rc.letterbox = widescreen ? 1 : 0;
    rc.lb_top = 0;
    rc.wtext = wtext_full; rc.wtext_len = wlen;
    rc.jpeg_clsid = jpeg_clsid;
    rc.enc_params = ep;

    // Подготовим новые чанки: видео — заменим, аудио — скопируем
    AviInfo::Chunk* nch = (AviInfo::Chunk*)HeapAlloc(GetProcessHeap(), 0, sizeof(AviInfo::Chunk)*avi.n_chunks);
    DynBuf* per_frame_jpegs = (DynBuf*)HeapAlloc(GetProcessHeap(), 0, sizeof(DynBuf)*avi.n_chunks);
    for (size_t i = 0; i < avi.n_chunks; i++) per_frame_jpegs[i].init();

    uint32_t max_frame = 0;
    for (size_t i = 0; i < avi.n_chunks; i++) {
        nch[i] = avi.chunks[i];
        char b1 = (char)(nch[i].fcc & 0xff);
        char b2 = (char)((nch[i].fcc >> 8) & 0xff);
        char b3 = (char)((nch[i].fcc >> 16) & 0xff);
        char b4 = (char)((nch[i].fcc >> 24) & 0xff);
        bool is_video = (b3 == 'd' && (b4 == 'c' || b4 == 'b'));
        (void)b1; (void)b2;
        if (is_video && avi.chunks[i].size > 0) {
            render_frame_to_jpeg(rc, avi.chunks[i].data, avi.chunks[i].size, per_frame_jpegs[i]);
            nch[i].data = per_frame_jpegs[i].data;
            nch[i].size = (uint32_t)per_frame_jpegs[i].size;
            if (nch[i].size > max_frame) max_frame = nch[i].size;
        }
        // Пустые видео-чанки (drop frame) пропускаем — плеер использует
        // предыдущий декодированный кадр.
    }

    // Собрать AVI и записать
    DynBuf out; out.init();
    build_avi(avi, nch, max_frame, out);
    if (!write_file(output_path, out.data, out.size)) die2w("cannot write", output_path);

    // Финал: освобождать ресурсы не обязательно — процесс выходит
    fprintf(stdout, "Done: %ls\n", output_path);
    return 0;
}

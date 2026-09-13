#ifndef FB_DEBUG_H
#define FB_DEBUG_H

#include <stdio.h>
#include <stdlib.h>

#ifdef FB_DEBUG
#define FB_DBG(...)      fprintf(stderr, "[FB] " __VA_ARGS__)
#define FB_DEBUG_ENABLED 1
#else
#define FB_DBG(...)      ((void)0)
#define FB_DEBUG_ENABLED 0
#endif

#ifdef FB_DEBUG
#define FB_TRACE(...)                                  \
    do                                                 \
    {                                                  \
        static int _fb_tr = -1;                        \
        if (_fb_tr < 0)                                \
        {                                              \
            const char *e = getenv("FAMILYBOX_TRACE"); \
            _fb_tr = (e && e[0] == '1') ? 1 : 0;       \
        }                                              \
        if (_fb_tr)                                    \
            fprintf(stderr, "[TR] " __VA_ARGS__);      \
    } while (0)
#define FB_TRACE_ENABLED 1
#else
#define FB_TRACE(...)    ((void)0)
#define FB_TRACE_ENABLED 0
#endif

/* Milliseconds since first call — proves logs are live, not a replay. */
#ifdef _WIN32
#include <windows.h>
static inline unsigned long fb_now_ms(void)
{
    static ULONGLONG t0 = 0;
    ULONGLONG now = GetTickCount64();
    if (t0 == 0)
        t0 = now;
    return (unsigned long)(now - t0);
}
#else
#include <time.h>
static inline unsigned long fb_now_ms(void)
{
    static long t0 = -1;
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    long now = ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
    if (t0 < 0)
        t0 = now;
    return (unsigned long)(now - t0);
}
#endif

#endif

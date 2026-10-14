#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* Ordered coverage crossfade for MONO1: unchanged pixels never change, and
 * each changed pixel switches once from the outgoing to the incoming image.
 * The endpoint is byte-exact. No gray framebuffer or transfer queue is used. */
static inline bool portable_paper_blend(uint8_t *incoming, size_t stride,
    const uint8_t *outgoing, size_t old_stride, unsigned width, unsigned height,
    unsigned coverage) {
    static const uint8_t bayer[4][4]={{0,8,2,10},{12,4,14,6},{3,11,1,9},{15,7,13,5}};
    if(!incoming || !outgoing || !width || !height || width>1024 || height>1024 ||
       stride<(width+7u)/8u || old_stride<(width+7u)/8u || coverage>16)return false;
    if(coverage==16)return true;
    for(unsigned y=0;y<height;++y) {
        uint8_t mask=0;
        for(unsigned x=0;x<8;++x)if(bayer[y&3u][x&3u]<coverage)mask|=(uint8_t)(0x80u>>x);
        for(unsigned x=0;x<(width+7u)/8u;++x) {
            uint8_t selected=mask;
            if(x==width/8u && (width&7u))selected|=(uint8_t)(0xffu>>(width&7u));
            incoming[y*stride+x]=(uint8_t)((incoming[y*stride+x]&selected)|(outgoing[y*old_stride+x]&~selected));
        }
    }
    return true;
}

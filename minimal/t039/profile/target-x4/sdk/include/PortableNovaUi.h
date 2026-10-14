#pragma once
#include <stdbool.h>
#include <stdint.h>
/* App-local presentation, linked with the portable adapter. No Runtime ABI,
 * provider calls, storage, allocation or navigation policy is added here. */
#define NOVA_CYAN 0x19e3ffu
#define NOVA_DIM 0x0e4f5cu
#define NOVA_LINE 0x12262bu
#define NOVA_CAP 0x6b8288u
#define NOVA_TEXT 0xcfe9eeu
#define NOVA_WHITE 0xffffffu
#define NOVA_MIN_TARGET 44
#define NOVA_FACE_ORBITRON_10 6u
void portable_nova_begin(void);
void portable_nova_text(unsigned face,int x,int y,int width,const char *text,uint32_t color);
void portable_nova_center(unsigned face,int x,int y,int width,const char *text,uint32_t color);
void portable_nova_right(unsigned face,int x,int y,int width,const char *text,uint32_t color);
int portable_nova_measure(unsigned face,const char *text);
void portable_nova_fill(int x,int y,int width,int height,uint32_t color);
void portable_nova_round(int x,int y,int width,int height,int radius,uint32_t color);
void portable_nova_button(int x,int y,int width,int height,const char *text,bool selected);
void portable_nova_row(int x,int y,int width,int height,const char *label,const char *value,bool selected);
void portable_nova_header(const char *title);
void portable_nova_rule(int x,int y,int width);
bool portable_nova_hit(int x,int y,int left,int top,int width,int height);

/* Returns true only if the entire bounded string fitted. A shortened last line
 * always ends with a visible ellipsis; stored text is never changed. */
bool portable_nova_wrap(unsigned face,int x,int y,int width,int line_height,unsigned max_lines,const char *text,uint32_t color);

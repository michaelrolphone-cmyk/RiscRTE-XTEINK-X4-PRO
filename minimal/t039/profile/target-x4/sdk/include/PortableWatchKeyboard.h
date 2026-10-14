#pragma once
/* Standard 32-key Watch keyboard, extracted without geometry/character changes
 * from Points in Time 0.4.2 (Productivity dbc8a8a1), points_watch_keyboard.h.
 * Its origin is the portable Watch Wi-Fi keyboard. Keep these shared hit cells,
 * three ASCII pages and action order stable. No eight-key NOVA pager. */
#define PWK_CHARACTERS 32u
#define PWK_PAGES 3u
#define PWK_PAGE 32u
#define PWK_DELETE 33u
#define PWK_DONE 34u
#define PWK_COUNT 35u
#define PWK_INITIAL_PAGE 2u
typedef struct {int x,y,w,h;} portable_watch_key_rect;
static inline unsigned portable_watch_key_character(unsigned page,unsigned key){
 if(page>=PWK_PAGES || key>=PWK_CHARACTERS)return 0;
 unsigned ch=32+page*PWK_CHARACTERS+key;return ch<=126?ch:0;
}
static inline int portable_watch_key_hit(int x,int y){
 if(x<0 || x>=240 || y<0 || y>=240)return -1;
 if(x>=12 && x<228 && y>=76 && y<172)return (y-76)/24*8+(x-12)/27;
 if(y>=178 && y<207 && x>=12 && x<228)return 32+(x-12)/72;
 return -1;
}
static inline int portable_watch_key_bounds(unsigned key,portable_watch_key_rect *out){
 if(!out || key>=PWK_COUNT)return 0;
 if(key<PWK_CHARACTERS)*out=(portable_watch_key_rect){12+(int)(key%8)*27,76+(int)(key/8)*24,25,22};
 else *out=(portable_watch_key_rect){12+(int)(key-32)*72,178,key==PWK_DONE?72:68,29};
 return 1;
}

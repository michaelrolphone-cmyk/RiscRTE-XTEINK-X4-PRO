#pragma once
/* A bounded printable-ASCII keyboard for the 240px Nova utility surface.
 * Eight >=44px character buttons, plus Prev / Next / Delete / Done.
 * Callers keep entry bytes, masking, limits and explicit Save/Cancel ownership. */
#define PORTABLE_NOVA_KEY_PAGES 12u
#define PORTABLE_NOVA_KEYS_PER_PAGE 8u
static inline unsigned portable_nova_key_character(unsigned page,unsigned key) {
    static const char characters[]="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 !\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
    unsigned index=page*PORTABLE_NOVA_KEYS_PER_PAGE+key;
    return page<PORTABLE_NOVA_KEY_PAGES && key<PORTABLE_NOVA_KEYS_PER_PAGE && index<sizeof(characters)-1?(unsigned char)characters[index]:0;
}

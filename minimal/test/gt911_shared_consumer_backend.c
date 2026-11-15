/* Physical I/O doubles only; the provider under test is the production source. */
#define main gt911_existing_fixture_main
#include "gt911_test.c"
#undef main

const risc_touch_api_v1 *multitouch_fixture_start(void) {
    driver = t5_driver_get(2); assert(driver); api = driver->capability;
    power = risc_touch_power(api); assert(power && start());
    return api;
}
void multitouch_fixture_report(const risc_touch_contact_v1 *points,
                              unsigned count, uint64_t ms) {
    assert(count <= 5); packet((uint8_t)count, 0, 0, false); time_ms = ms;
    for (unsigned i = 0; i < count; ++i) {
        assert(points[i].id >= 1 && points[i].id <= 16);
        wire_point(i, (uint8_t)(points[i].id - 1u), points[i].x, points[i].y);
    }
}
void multitouch_fixture_ack(bool okay) { ack_ok = okay; }
void multitouch_fixture_stop(void) { done(0); }

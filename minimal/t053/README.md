# T053 cumulative USB storage

Build on verified 0.1.117 with unchanged native a91edf3fada6a559ec107186dd163d0c8da10d29. Replace only USB app (0.1.10 to 0.1.11), shared MSC (0.1.7 to 0.1.8), boot image hash and cohort metadata. Preserve all old changed-SD files, add the new MSC hash image and update its manifest. Home, clock, Points, OBDTest and Buttons are preserved.

All 43 internal ELFs pass native import/role/structure checks; full Runtime/CpuPort cohort admission passes under UBSan with zero hardware/storage calls. Shared MSC and native PHY/serial lifecycle tests pass ASan/UBSan; actual Waveshare SD + shared MSC integration passes. No hardware speed or reconnection qualification is claimed. Windows host safe eject remains the normal workflow.

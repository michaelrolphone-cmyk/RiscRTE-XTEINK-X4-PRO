# Mounted Files .97 focused hosted checks

The working-branch CI follow-up changes only tests, its workflow and build records.
The shipped candidate remains built from public product source
`e9332c3fe731ed63508e223bcd67cedf481462e4`; its BIN SHA256 remains
`d18ad4726d6503b53a17c556cc1e8bc6a40769885c7c60c176b393707a499dd6`.
No image is rebuilt or reidentified for this test-only follow-up.

The standalone job verifies final recipe/source locks, the immutable final image
receipt, sixteen authority grants, eight fail-closed publication guards and the
existing shared-settings composition tests. Both historical Reader recipe checks
failed identically on delivered .96 and product e933 because their product-version
allowlists ended at .90. Only .96 and .97 are added to those allowlists. The exact
Reader version, source, baseline image, native, panel and link provenance
assertions remain unchanged and pass.

A separate target job rebuilds Files 1.5.31 from published System source
`0accd8905b5a64bf5e9269fe92a6e47c9fd1cc90`, using the exact Xtensa compiler and
pinned native-time and resident SDK inputs. It checks the resulting ELF and
manifest byte hashes, all 312 compiled-source hashes and the complete build
receipt except its machine-local resident SDK directory. No firmware or user
computer is involved, and no generated binary is uploaded by this workflow.

Hosted checks do not have the private delivered .96 full BIN/SD baseline. They
therefore do not claim whole-image admission, provider execution or hardware
qualification. The separate final .97 local receipt records independent 16 MiB
readback, all preserved ranges, 42 internal and 46 selected SD ELF admissions,
215 preservation/publication-gate probes and seven filesystem replay plans.

# Contributing

Install the Linux toolchain from README, build with `make build`, and run `make test` before proposing a change. Networking tests launch real child processes and use dynamically selected localhost ports. Never replace these with simulated success responses.

Keep packet encoding backwards compatible or introduce an explicit protocol version. Add corruption/bounds checks for codec changes and real-process integration coverage for route/transport changes. Preserve accurate observed metrics; distinguish generated workloads from measured results. Document unsupported features in `docs/FEATURE_STATUS.md`.

Do not commit `.runtime`, shared keys, session tokens, local reports or compiled binaries. For a PR, describe the behavioral change, setup implications and exact verification performed. C++20, OpenSSL and Python standard-library portability are intentional constraints of this release.

| model                          |       size |     params | backend    | ngl | threads | dev          |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | --: | ------: | ------------ | --------------: | -------------------: |
| qwen35 0.8B Q4_0               | 478.76 MiB |   772.85 M | OpenCL,HTP |  -1 |       4 | none         |           pp128 |        453.55 ± 0.86 |
| qwen35 0.8B Q4_0               | 478.76 MiB |   772.85 M | OpenCL,HTP |  -1 |       4 | none         |            tg64 |         79.51 ± 0.77 |
| qwen35 2B Q4_0                 |   1.14 GiB |     1.94 B | OpenCL,HTP |  -1 |       4 | none         |           pp128 |        195.69 ± 4.78 |
| qwen35 2B Q4_0                 |   1.14 GiB |     1.94 B | OpenCL,HTP |  -1 |       4 | none         |            tg64 |         28.21 ± 7.12 |

build: 7fe450e19 (11146)

FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Common to O2..O4: performance governor by default, tickless/RCU offload support
# (inactive until nohz_full=/rcu_nocbs= are given on the cmdline), cpusets, USB audio.
SRC_URI:append = " file://vieedge-common.cfg"

# Latency tracers (timerlat/osnoise) for the measurement build; VIEEDGE_TRACING = "0" for the throughput build.
SRC_URI:append = "${@' file://vieedge-tracing.cfg' if d.getVar('VIEEDGE_TRACING') == '1' else ' file://vieedge-notrace.cfg'}"

# O3/O4: fully preemptible kernel (mainline PREEMPT_RT since 6.12, arm64 supported).
SRC_URI:append = "${@' file://preempt-rt.cfg' if d.getVar('VIEEDGE_RT') == '1' else ''}"

LINUX_VERSION_EXTENSION:append = "${@'-rt' if d.getVar('VIEEDGE_RT') == '1' else ''}"

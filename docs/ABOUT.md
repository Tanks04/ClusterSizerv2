# About this project

ClusterSizer came out of one specific, boring problem: a sysadmin puts
together the HW for a new cluster, and has to manually add up CPU, RAM,
storage, and network ports in Excel, for the third time that year, from
scratch every time.

The tool was built through a collaboration between a human and an AI
(Claude, Anthropic) - and that's stated on purpose, not hidden in fine
print, because we think that's a normal way to work today.

Roughly, the split went like this: the idea, the requirements, the
sysadmin-level judgment ("DR replicas often aren't 1:1", "need Ctrl+click
for multi-select", "don't let someone accidentally import VMs under
Servers") - all of that came from a human who actually does this job. The
code architecture, writing the Python/Qt itself, testing, and debugging -
that was mostly the AI, with a human reviewing every step, asking for
fixes, and rejecting what wasn't good enough.

Neither side deserves all the credit here, so neither claims it. The tool
is public and free specifically so it can be useful to others solving the
same boring problem - not as a demo of anything.

If you run into a bug or have an idea for v3 - issues/PRs are welcome.

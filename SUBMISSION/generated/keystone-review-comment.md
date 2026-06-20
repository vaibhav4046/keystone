## Keystone Review Gate: BLOCK

This merge request changes `compute_blast_radius` (`core/impact.py`).

**Git result:** No textual conflict detected.

**Orbit result:** Hidden dependency blast radius detected.

**Impact (engine-computed from the Orbit graph):**

* Direct affected definitions (ring-1): **12**
* Total affected definitions: **12**
* Files: **6**
* Directories: **4**
* Policy tier: **CROSS_TEAM**
* Required approvers: **2**
* Review window: **24h advisory**

**Decision: BLOCK**

**Why Keystone blocked it:**

* Git sees no textual conflict.
* GitLab Orbit found dependency overlap across the blast radius.
* A matching blast signature was previously rejected (Antigravity rejected KS-compute_blast_radius).

**Required action:** Do not merge until owner review and a recorded precedent override are in place.

---
_Engine computed. AI explanation only. Same graph + same policy = same decision._

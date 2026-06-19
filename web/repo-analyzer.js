/* ==========================================================================
   Keystone — client-side repo analyzer.
   Point Keystone at ANY public GitHub repo and build its call graph + blast
   radius entirely in the browser. No backend, no signup. This is a static,
   regex-based Python approximation (dynamic dispatch is under-approximated -
   the same honest limit the Orbit backend concedes); it produces the exact
   data shape the existing engine consumes (STATIC.definitions + STATIC.impact),
   so the symbol rail, blast graph, IMPACT panel and collision builder all work
   on the user's own code.
   Exposes: window.analyzeRepo(url, onProgress) -> Promise<staticShape>
   ========================================================================== */
(function () {
  "use strict";

  var MAX_FILES = 160;          // cap fetched .py files
  var MAX_FILE_BYTES = 240000;  // skip very large files
  var MAX_DEFS = 1200;          // cap symbols
  var FETCH_CONCURRENCY = 12;

  function parseRepoUrl(raw) {
    var s = String(raw || "").trim().replace(/^https?:\/\/(www\.)?github\.com\//i, "").replace(/\.git$/i, "");
    s = s.replace(/^github\.com\//i, "");
    var treeM = s.match(/^([^\/]+)\/([^\/]+)\/tree\/([^\/]+)/);
    if (treeM) return { owner: treeM[1], repo: treeM[2], branch: treeM[3] };
    var m = s.match(/^([^\/\s]+)\/([^\/\s]+)/);
    if (!m) return null;
    return { owner: m[1], repo: m[2], branch: "" };
  }

  function ghJson(url) {
    return fetch(url, { headers: { "Accept": "application/vnd.github+json" } }).then(function (r) {
      if (r.status === 403) throw new Error("GitHub API rate limit hit (60/hr unauthenticated). Try again shortly, or a smaller repo.");
      if (r.status === 404) throw new Error("Repo or branch not found. Use a public repo, e.g. pallets/click.");
      if (!r.ok) throw new Error("GitHub API error " + r.status);
      return r.json();
    });
  }

  function resolveBranch(owner, repo, branch) {
    if (branch) return Promise.resolve(branch);
    return ghJson("https://api.github.com/repos/" + owner + "/" + repo).then(function (info) {
      return info.default_branch || "main";
    });
  }

  function listPyFiles(owner, repo, branch) {
    return ghJson("https://api.github.com/repos/" + owner + "/" + repo + "/git/trees/" + encodeURIComponent(branch) + "?recursive=1")
      .then(function (tree) {
        var files = (tree.tree || []).filter(function (t) {
          return t.type === "blob" && /\.py$/.test(t.path) && (t.size || 0) <= MAX_FILE_BYTES
            && !/(^|\/)(\.|node_modules\/|venv\/|site-packages\/)/.test(t.path);
        });
        files.sort(function (a, b) {
          var at = /test/i.test(a.path) ? 1 : 0, bt = /test/i.test(b.path) ? 1 : 0;
          return at - bt || (a.size || 0) - (b.size || 0);
        });
        return { files: files.slice(0, MAX_FILES), truncated: files.length > MAX_FILES, total: files.length };
      });
  }

  function fetchRaw(owner, repo, branch, path) {
    return fetch("https://raw.githubusercontent.com/" + owner + "/" + repo + "/" + branch + "/" + path)
      .then(function (r) { return r.ok ? r.text() : ""; }).catch(function () { return ""; });
  }

  function fetchAll(owner, repo, branch, files, onProgress) {
    var out = [], i = 0, done = 0;
    return new Promise(function (resolve) {
      function next() {
        if (i >= files.length) { if (done >= files.length) resolve(out); return; }
        var f = files[i++];
        fetchRaw(owner, repo, branch, f.path).then(function (text) {
          if (text) out.push({ path: f.path, text: text });
          done++;
          if (onProgress) onProgress("Reading " + done + "/" + files.length + " files…");
          next();
        });
      }
      for (var k = 0; k < Math.min(FETCH_CONCURRENCY, files.length); k++) next();
      if (!files.length) resolve(out);
    });
  }

  var KW = { "if": 1, "for": 1, "while": 1, "with": 1, "return": 1, "print": 1, "and": 1, "or": 1, "not": 1, "in": 1, "is": 1, "len": 1, "str": 1, "int": 1, "dict": 1, "list": 1, "set": 1, "tuple": 1, "super": 1, "isinstance": 1, "range": 1, "enumerate": 1, "open": 1, "self": 1, "assert": 1, "raise": 1, "except": 1, "elif": 1, "lambda": 1, "yield": 1, "type": 1, "format": 1, "join": 1, "bool": 1, "float": 1, "getattr": 1, "setattr": 1, "hasattr": 1, "map": 1, "filter": 1, "sorted": 1, "min": 1, "max": 1, "sum": 1, "any": 1, "all": 1, "zip": 1 };

  function parsePy(file, text) {
    var lines = text.split(/\r?\n/);
    var defs = [];
    var defRe = /^(\s*)(def|class)\s+([A-Za-z_]\w*)/;
    for (var ln = 0; ln < lines.length; ln++) {
      var m = lines[ln].match(defRe);
      if (m) {
        var indent = m[1].replace(/\t/g, "    ").length;
        defs.push({ name: m[3], rawKind: m[2], indent: indent, file: file, line: ln + 1, start: ln, end: lines.length, calls: {} });
      }
    }
    for (var d = 0; d < defs.length; d++) {
      var def = defs[d];
      for (var j = def.start + 1; j < lines.length; j++) {
        var raw = lines[j];
        if (!raw.trim()) continue;
        var ind = (raw.match(/^(\s*)/)[1] || "").replace(/\t/g, "    ").length;
        if (ind <= def.indent) { def.end = j; break; }
      }
    }
    defs.forEach(function (def) {
      var kind = def.rawKind === "class" ? "Class" : "Function";
      if (def.rawKind === "def" && def.indent > 0) {
        for (var e = 0; e < defs.length; e++) {
          var o = defs[e];
          if (o.rawKind === "class" && o.indent < def.indent && def.start > o.start && def.start < o.end) { kind = "Method"; break; }
        }
      }
      def.kind = kind;
      var callRe = /([A-Za-z_]\w*)\s*\(/g, mm;
      for (var j2 = def.start + 1; j2 < def.end; j2++) {
        var lraw = lines[j2];
        if (/^\s*#/.test(lraw)) continue;
        while ((mm = callRe.exec(lraw))) {
          var nm = mm[1];
          if (KW[nm]) continue;
          if (nm === def.name) continue;
          def.calls[nm] = 1;
        }
      }
    });
    return defs;
  }

  function fnv(s) { var h = 0x811c9dc5; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = (h * 0x01000193) >>> 0; } return ("" + h); }

  function sha256Hex(str) {
    if (!(window.crypto && window.crypto.subtle)) return Promise.resolve(fnv(str).padStart(16, "0"));
    var buf = new TextEncoder().encode(str);
    return window.crypto.subtle.digest("SHA-256", buf).then(function (dg) {
      return Array.prototype.map.call(new Uint8Array(dg), function (b) { return b.toString(16).padStart(2, "0"); }).join("");
    }).catch(function () { return fnv(str).padStart(16, "0"); });
  }

  function buildModel(allDefs) {
    if (allDefs.length > MAX_DEFS) allDefs = allDefs.slice(0, MAX_DEFS);
    var nameToIds = {}, byId = {};
    allDefs.forEach(function (def, idx) {
      def.id = idx + 1;
      byId[def.id] = def;
      (nameToIds[def.name] = nameToIds[def.name] || []).push(def.id);
    });
    var callers = {};
    allDefs.forEach(function (def) { callers[def.id] = {}; });
    allDefs.forEach(function (def) {
      Object.keys(def.calls).forEach(function (nm) {
        var ids = nameToIds[nm];
        if (!ids || !ids.length) return;
        var target = null;
        for (var i = 0; i < ids.length; i++) { if (byId[ids[i]].file === def.file) { target = ids[i]; break; } }
        if (target == null) target = ids[0];
        if (target === def.id) return;
        callers[target][def.id] = 1;
      });
    });
    return { defs: allDefs, byId: byId, callers: callers };
  }

  function ringsFor(model, rootId, maxRing) {
    var seen = {}; seen[rootId] = 0;
    var rings = { 0: [rootId] };
    var frontier = [rootId], ring = 0;
    while (frontier.length && ring < maxRing) {
      ring++;
      var next = [];
      frontier.forEach(function (id) {
        Object.keys(model.callers[id] || {}).forEach(function (cid) {
          cid = Number(cid);
          if (seen[cid] === undefined) { seen[cid] = ring; (rings[ring] = rings[ring] || []).push(cid); next.push(cid); }
        });
      });
      frontier = next;
    }
    return rings;
  }

  function tierFor(n) { return n >= 8 ? "CROSS_TEAM" : (n >= 2 ? "LOCAL" : "ISOLATED"); }

  function toStatic(model, meta) {
    var defs = model.defs;
    var names = defs.map(function (d) { return d.name; });
    var details = {}, impact = {}, impactPromises = [];
    var nameById = {}; defs.forEach(function (d) { nameById[d.id] = d.name; });

    defs.forEach(function (def) {
      var rings = ringsFor(model, def.id, 6);
      var affected = [];
      Object.keys(rings).forEach(function (r) { if (Number(r) > 0) affected = affected.concat(rings[r]); });
      var total = affected.length;
      var ringObj = {}; Object.keys(rings).forEach(function (r) { ringObj[r] = rings[r]; });
      var namesMap = {}; namesMap[def.id] = def.name; affected.forEach(function (id) { namesMap[id] = nameById[id]; });
      var owners = [{ id: def.id, file: def.file, dir: def.file.replace(/\/[^\/]*$/, "") }];
      affected.forEach(function (id) { var dd = model.byId[id]; owners.push({ id: id, file: dd.file, dir: dd.file.replace(/\/[^\/]*$/, "") }); });
      var files = {}; affected.forEach(function (id) { files[model.byId[id].file] = 1; });
      var tier = tierFor(total);
      var imp = {
        epicenter: { id: def.id, name: def.name, fqn: def.file.replace(/\.py$/, "").replace(/\//g, ".") + "." + def.name, file: def.file, kind: def.kind },
        rings: ringObj, affected_ids: affected,
        counts: { ring_1: (rings[1] || []).length, total_affected: total, unaffected: Math.max(0, defs.length - 1 - total) },
        signature: "", owners: owners, names: namesMap, parents: {},
        policy: {
          tier: tier, action: "ALLOW", counts: { total_affected: total },
          affected_files: Object.keys(files), affected_directories: [],
          required_approvers: tier === "CROSS_TEAM" ? 2 : 1, review_window_hours: tier === "CROSS_TEAM" ? 24 : 0,
          required_owner: null,
          reasons: [total + " dependent definition" + (total === 1 ? "" : "s") + " across " + Object.keys(files).length + " file" + (Object.keys(files).length === 1 ? "" : "s") + " -> tier " + tier],
          policy_version: "client-1", policy_hash: ""
        },
        orbit_snapshot_sha256: meta.sha, orbit_crosscheck: null
      };
      impact[def.name] = imp;
      details[def.name] = { kind: def.kind, tier: tier, action: "ALLOW", total_affected: total };
      impactPromises.push(sha256Hex(def.id + ":" + affected.slice().sort(function (a, b) { return a - b; }).join(",")).then(function (h) { imp.signature = h; }));
    });

    return Promise.all(impactPromises).then(function () {
      return {
        static: true,
        status: {
          source_mode: "REPO", definitions: defs.length, orbit_access: "client static analysis",
          orbit_verified_symbols: 0, duckdb_path: meta.slug, audit_chain: { ok: true, count: 0 },
          integrity: { hmac: false, open_mode: true, reviewer_verified: false }, window_enforced: false,
          data_provenance: "Client-side static analysis of " + meta.slug + " (" + defs.length + " Python definitions across " + meta.fileCount + " files). Regex-based call graph - an honest approximation; Python dynamic dispatch is under-approximated."
        },
        definitions: { names: names, details: details },
        impact: impact, precedent: {}, brief: {}, assistant: {}, policy: {}, agents: {},
        attestation: {}, audit: { rows: [], ok: true }, collisions: null, graph_audit: null, harness: null,
        _repo: meta
      };
    });
  }

  window.analyzeRepo = function (url, onProgress) {
    var p = parseRepoUrl(url);
    if (!p) return Promise.reject(new Error("Use owner/repo or a github.com URL, e.g. pallets/click"));
    var slug = p.owner + "/" + p.repo;
    if (onProgress) onProgress("Resolving " + slug + "…");
    return resolveBranch(p.owner, p.repo, p.branch).then(function (branch) {
      p.branch = branch;
      if (onProgress) onProgress("Listing Python files…");
      return listPyFiles(p.owner, p.repo, branch);
    }).then(function (listed) {
      if (!listed.files.length) throw new Error("No Python files found in " + slug + " (this analyzer reads .py). Try a Python repo, e.g. pallets/click.");
      if (onProgress) onProgress("Found " + listed.total + " Python files" + (listed.truncated ? " (analyzing first " + MAX_FILES + ")" : "") + "…");
      return fetchAll(p.owner, p.repo, p.branch, listed.files, onProgress).then(function (fetched) {
        if (onProgress) onProgress("Parsing call graph from " + fetched.length + " files…");
        var allDefs = [];
        fetched.forEach(function (f) { var ds = parsePy(f.path, f.text); for (var i = 0; i < ds.length; i++) allDefs.push(ds[i]); });
        if (!allDefs.length) throw new Error("Parsed no definitions from " + slug + ".");
        var model = buildModel(allDefs);
        if (onProgress) onProgress("Computing blast radii for " + model.defs.length + " symbols…");
        return sha256Hex(slug + ":" + p.branch).then(function (sha) {
          return toStatic(model, { slug: slug, branch: p.branch, fileCount: fetched.length, sha: sha.slice(0, 16) });
        });
      });
    });
  };
})();

/* In-browser real Orbit SQL.
   Lazy-loads duckdb-wasm (the SAME engine Orbit uses) ON DEMAND, loads the committed
   real Orbit edges/defs, and runs the LITERAL reverse-CALLS ring-1 query in the judge's
   own browser - no backend, no precomputed answer. Exposes:
     window.__ksRunOrbitSQL(symbolName) -> Promise<{ symbol, count, sql, engine }>
   Throws on any failure so the caller can fall back to the live backend query.
   BIGINT-safe: the 19-digit gl_definition ids are parsed inside WASM (duckdb read_json),
   never by JS, so precision is preserved. */
(function () {
  "use strict";
  var DUCKDB_ESM = "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.29.0/+esm";
  var _dbP = null; // memoized {db, conn}

  // The literal query a judge can read - identical semantics to core/graph.direct_callers
  // and the backend's /api/impact ring_1 cross-check.
  var SQL_TEMPLATE =
    "SELECT count(DISTINCT e.source_id) AS n\n" +
    "FROM gl_edge e JOIN gl_definition d ON e.target_id = d.id\n" +
    "WHERE d.name = '<SYMBOL>' AND e.relationship_kind = 'CALLS'\n" +
    "  AND e.source_kind = 'Definition' AND e.target_kind = 'Definition'\n" +
    "  AND e.source_id <> e.target_id";

  function _init() {
    if (_dbP) return _dbP;
    _dbP = (async function () {
      var duckdb = await import(/* @vite-ignore */ DUCKDB_ESM);
      var bundles = duckdb.getJsDelivrBundles();
      // Force the MVP (single-threaded) bundle: the threaded COI bundle needs
      // SharedArrayBuffer + COOP/COEP headers a static host (GitHub Pages) cannot set,
      // which traps with "unreachable". MVP runs anywhere.
      var bundle = bundles.mvp || (await duckdb.selectBundle(bundles));
      var workerUrl = URL.createObjectURL(
        new Blob(['importScripts("' + bundle.mainWorker + '");'], { type: "text/javascript" }));
      var worker = new Worker(workerUrl);
      var db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(), worker);
      await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
      URL.revokeObjectURL(workerUrl);
      var conn = await db.connect();
      var edges = new Uint8Array(await (await fetch("orbit_edges.csv")).arrayBuffer());
      var defs = new Uint8Array(await (await fetch("orbit_defs.csv")).arrayBuffer());
      await db.registerFileBuffer("orbit_edges.csv", edges);
      await db.registerFileBuffer("orbit_defs.csv", defs);
      // read_csv_auto is built into duckdb core (no extension); duckdb parses the bytes
      // in-WASM so the 19-digit BIGINT ids keep full precision (JS never parses them).
      await conn.query("CREATE TABLE gl_edge AS SELECT * FROM read_csv_auto('orbit_edges.csv', header=true)");
      await conn.query("CREATE TABLE gl_definition AS SELECT * FROM read_csv_auto('orbit_defs.csv', header=true)");
      return { db: db, conn: conn };
    })().catch(function (e) { _dbP = null; throw e; });
    return _dbP;
  }

  window.__ksRunOrbitSQL = async function (symbol) {
    var name = String(symbol || "").replace(/'/g, "''");
    var ctx = await _init();
    var sql = SQL_TEMPLATE.replace("<SYMBOL>", name);
    var res = await ctx.conn.query(sql);
    var rows = res.toArray();
    var n = rows && rows.length ? Number(rows[0].n) : 0;
    return { symbol: symbol, count: n, sql: sql, engine: "duckdb-wasm (in your browser)" };
  };
})();

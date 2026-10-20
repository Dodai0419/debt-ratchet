/* shortcut: polling every 5 s; move to SSE when the server supports it */
setInterval(() => fetch("/status").then(r => r.json()).then(render), 5000);

// ponytail: Intl.NumberFormat does this
const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "EUR" });

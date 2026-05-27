import { createReadStream } from "node:fs";
import { access, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";

const host = process.env.HOST || "0.0.0.0";
const port = Number.parseInt(process.env.PORT || "4173", 10);
const root = resolve(process.cwd(), process.env.STATIC_DIR || "docs/.vitepress/dist");

const mimeTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".gif", "image/gif"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".jpeg", "image/jpeg"],
  [".jpg", "image/jpeg"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".map", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".webp", "image/webp"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);

function withinRoot(pathname) {
  return pathname === root || pathname.startsWith(`${root}${sep}`);
}

function toSafePath(urlPathname) {
  const decoded = decodeURIComponent(urlPathname);
  const normalized = normalize(decoded).replace(/^(\.\.[/\\])+/, "");
  const absolute = resolve(join(root, normalized));

  if (!withinRoot(absolute)) {
    return null;
  }

  return absolute;
}

async function exists(pathname) {
  try {
    await access(pathname);
    return true;
  } catch {
    return false;
  }
}

async function resolveAsset(urlPathname) {
  const safePath = toSafePath(urlPathname);

  if (!safePath) {
    return null;
  }

  const safeStat = await stat(safePath).catch(() => null);

  if (safeStat?.isDirectory()) {
    const indexPath = join(safePath, "index.html");
    return (await exists(indexPath)) ? indexPath : null;
  }

  if (safeStat?.isFile()) {
    return safePath;
  }

  if (!extname(safePath)) {
    const htmlPath = `${safePath}.html`;
    if (await exists(htmlPath)) {
      return htmlPath;
    }

    const indexPath = join(safePath, "index.html");
    if (await exists(indexPath)) {
      return indexPath;
    }
  }

  return null;
}

createServer(async (request, response) => {
  try {
    const requestUrl = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
    const assetPath = await resolveAsset(requestUrl.pathname);

    if (!assetPath) {
      response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    const extension = extname(assetPath);
    const headers = {
      "content-type": mimeTypes.get(extension) || "application/octet-stream",
    };

    if (assetPath.includes(`${sep}assets${sep}`)) {
      headers["cache-control"] = "public, max-age=31536000, immutable";
    }

    response.writeHead(200, headers);
    createReadStream(assetPath).pipe(response);
  } catch (error) {
    console.error(error);
    response.writeHead(500, { "content-type": "text/plain; charset=utf-8" });
    response.end("Internal server error");
  }
}).listen(port, host, () => {
  console.log(`Learning Portal is serving ${root} at http://${host}:${port}`);
});

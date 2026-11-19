import { BrowserWindow, Updater, Utils, PATHS } from "electrobun/main";
import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

const DEV_SERVER_URL = "http://localhost:5173";
const IS_WIN = process.platform === "win32";

// ---------------------------------------------------------------------------
// Python backend (sidecar)
// ---------------------------------------------------------------------------
// Packaged app: the PyInstaller onedir build is copied to Resources/app/sidecar.
// Dev: run server.py from the repo root with uv.
function spawnBackend(): Bun.Subprocess<"ignore", "pipe", "inherit"> {
	const env = {
		...process.env,
		DHAMMA_NO_BROWSER: "1",
	};
	const bundled = join(
		PATHS.RESOURCES_FOLDER,
		"app",
		"sidecar",
		IS_WIN ? "DhammaStudio.exe" : "DhammaStudio",
	);
	if (existsSync(bundled)) {
		console.log(`Starting bundled backend: ${bundled}`);
		return Bun.spawn([bundled], { env, stdout: "pipe", stderr: "inherit" });
	}
	const repoRoot = resolve(import.meta.dir, "../../..");
	console.log(`Starting dev backend via uv in ${repoRoot}`);
	return Bun.spawn(["uv", "run", "python", "server.py"], {
		cwd: repoRoot,
		env,
		stdout: "pipe",
		stderr: "inherit",
	});
}

/** Resolve the port once the backend prints DHAMMA_STUDIO_PORT=<n>. Keeps echoing logs. */
async function readPort(proc: Bun.Subprocess<"ignore", "pipe", "inherit">): Promise<number> {
	const reader = proc.stdout.getReader();
	const decoder = new TextDecoder();
	let buffer = "";
	let port = 0;
	let resolved: ((p: number) => void) | null = null;
	const portPromise = new Promise<number>((res) => (resolved = res));

	(async () => {
		while (true) {
			const { value, done } = await reader.read();
			if (done) break;
			const chunk = decoder.decode(value, { stream: true });
			process.stdout.write(chunk);
			if (!port) {
				buffer += chunk;
				const m = buffer.match(/DHAMMA_STUDIO_PORT=(\d+)/);
				if (m) {
					port = Number(m[1]);
					resolved?.(port);
				}
			}
		}
	})();

	const timeout = new Promise<number>((_, rej) =>
		setTimeout(() => rej(new Error("Backend did not report a port in time")), 180_000),
	);
	return Promise.race([portPromise, timeout]);
}

async function waitForBackend(base: string): Promise<void> {
	for (let i = 0; i < 600; i++) {
		try {
			const r = await fetch(`${base}/api/status`, { cache: "no-store" });
			if (r.ok) return;
		} catch {}
		await Bun.sleep(300);
	}
	throw new Error("Backend never became ready");
}

const backend = spawnBackend();
let quitting = false;

function quitApp(code = 0) {
	if (quitting) return;
	quitting = true;
	try {
		backend.kill();
	} catch {}
	Utils.quit(code);
}

// Backend exit (e.g. UI "Quit" button or crash) ends the app.
backend.exited.then(() => quitApp(0));
process.on("exit", () => {
	try {
		backend.kill();
	} catch {}
});

const port = await readPort(backend);
const apiBase = `http://127.0.0.1:${port}`;
await waitForBackend(apiBase);

// ---------------------------------------------------------------------------
// UI (Vite build bundled as views://, or the Vite dev server for HMR)
// ---------------------------------------------------------------------------
async function getMainViewUrl(): Promise<string> {
	const query = `?api=${encodeURIComponent(apiBase)}`;
	const channel = await Updater.localInfo.channel();
	if (channel === "dev") {
		try {
			await fetch(DEV_SERVER_URL, { method: "HEAD" });
			console.log(`HMR enabled: Using Vite dev server at ${DEV_SERVER_URL}`);
			return `${DEV_SERVER_URL}/${query}`;
		} catch {
			console.log("Vite dev server not running. Run 'hutch run dev:hmr' for HMR support.");
		}
	}
	return `views://mainview/index.html${query}`;
}

const mainWindow = new BrowserWindow({
	title: "Dhamma Studio — by joinworkify",
	url: await getMainViewUrl(),
	frame: { width: 1360, height: 900, x: 120, y: 80 },
});

// Closing the window asks the backend to shut down gracefully (an active
// render is allowed to finish); the exit handler above then quits the app.
mainWindow.on("close", async () => {
	try {
		await fetch(`${apiBase}/api/shutdown`, { method: "POST" });
	} catch {
		quitApp(0);
	}
});

console.log("Dhamma Studio desktop started");

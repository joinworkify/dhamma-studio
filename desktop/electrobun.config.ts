import type { ElectrobunConfig } from "electrobun";

export default {
	app: {
		name: "Dhamma Studio",
		identifier: "dev.joinworkify.dhammastudio",
		version: "0.5.1",
	},
	runtime: {
		// The backend's exit (or window close -> graceful shutdown) ends the app.
		exitOnLastWindowClosed: false,
	},
	build: {
		mainProcess: "bun",
		bun: {
			entrypoint: "src/bun/index.ts",
		},
		copy: {
			"dist/index.html": "views/mainview/index.html",
			"dist/assets": "views/mainview/assets",
			"dist/fonts": "views/mainview/fonts",
			// PyInstaller onedir backend (build with scripts/build_mac.sh first).
			"../dist/DhammaStudio": "sidecar",
		},
		watchIgnore: ["dist/**"],
		mac: {
			bundleCEF: false,
			icons: "icon.iconset",
			// Real signing: set ELECTROBUN_DEVELOPER_ID (and ELECTROBUN_APPLEID,
			// ELECTROBUN_APPLEIDPASS, ELECTROBUN_TEAMID for notarization) with a
			// joinworkify Apple Developer ID. Without them, scripts/package-mac.sh
			// falls back to a valid ad-hoc signature.
			codesign: !!process.env.ELECTROBUN_DEVELOPER_ID,
			notarize: !!process.env.ELECTROBUN_APPLEIDPASS,
		},
		linux: {
			bundleCEF: false,
		},
		win: {
			bundleCEF: false,
		},
	},
} satisfies ElectrobunConfig;

import { defineConfig } from "vite";
import { resolve } from "node:path";
import tailwindcss from "@tailwindcss/vite";
import { electrobunViteAliases } from "./.hutch/devkit/api/config/electrobun-vite";

export default defineConfig({
	plugins: [tailwindcss()],
	resolve: {
		alias: electrobunViteAliases(resolve(__dirname, ".hutch/devkit")),
	},
	root: "src/mainview",
	publicDir: "public",
	base: "./",
	build: {
		outDir: "../../dist",
		emptyOutDir: true,
	},
	server: {
		port: 5173,
		strictPort: true,
	},
});

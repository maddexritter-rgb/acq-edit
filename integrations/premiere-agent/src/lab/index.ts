import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { UxpWebSocketBridge } from "../bridge/uxp-websocket-bridge.js";
import { createLab } from "./server.js";
const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const runtimeRoot = path.join(root, "lab/runtime");
const config = JSON.parse(
  readFileSync(path.join(runtimeRoot, "config.json"), "utf8"),
);
// Fixed isolated configuration: inherited production environment must not redirect a backend.
process.env.PREMIERE_TEMP_DIR = path.join(runtimeRoot, "mailbox");
process.env.PREMIERE_MCP_CAPABILITIES = "inspect,edit,export,filesystem";
process.env.PREMIERE_MCP_TELEMETRY = "off";
const uxp = new UxpWebSocketBridge({
  token: config.token,
  port: config.port,
  path: "/lab-uxp",
});
if (process.env.PREMIERE_AGENT_UXP_LISTEN === '1') await uxp.start();
const { server } = createLab(root, runtimeRoot, uxp);
await server.connect(new StdioServerTransport());
const close = async () => {
  await server.close();
  await uxp.stop();
  process.exit(0);
};
process.once("SIGTERM", close);
process.once("SIGINT", close);

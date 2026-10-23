import {
  mkdirSync,
  readFileSync,
  writeFileSync,
  cpSync,
  existsSync,
  chmodSync,
} from "node:fs";
import { randomBytes } from "node:crypto";
import path from "node:path";
const root = process.cwd(),
  runtime = path.join(root, "lab/runtime"),
  packages = path.join(root, "lab/packages");
mkdirSync(runtime, { recursive: true, mode: 0o700 });
chmodSync(runtime, 0o700);
for (const d of ["mailbox", "fixtures", "operations"])
  mkdirSync(path.join(runtime, d), { recursive: true, mode: 0o700 });
const configPath = path.join(runtime, "config.json");
if (!existsSync(configPath))
  writeFileSync(
    configPath,
    JSON.stringify(
      {
        schema: "premiere-agent-lab/config-v1",
        token: randomBytes(32).toString("hex"),
        port: 17877,
      },
      null,
      2,
    ),
    { mode: 0o600 },
  );
const config = JSON.parse(readFileSync(configPath, "utf8"));
for (const [source, destination] of [
  ["cep-plugin", "PremiereAgentLabCEP"],
  ["uxp-plugin", "PremiereAgentLabUXP"],
])
  cpSync(path.join(root, source), path.join(packages, destination), {
    recursive: true,
  });
const cep = path.join(packages, "PremiereAgentLabCEP"),
  uxp = path.join(packages, "PremiereAgentLabUXP");
let file = path.join(cep, "CSXS/manifest.xml"),
  text = readFileSync(file, "utf8");
text = text
  .replace(
    /    <Extension Id="com\.mcp\.premiere\.bridge\.headless"[^>]*\/>\n/g,
    "",
  )
  .replace(
    /    <Extension Id="com\.mcp\.premiere\.bridge\.headless">[\s\S]*?<\/Extension>\n/g,
    "",
  );
text = text
  .replaceAll("com.mcp.premiere.bridge", "com.premiereagent.lab.bridge")
  .replaceAll("MCP Bridge", "Premiere Agent Lab")
  .replaceAll("MCP for Adobe Premiere Pro", "Premiere Agent Lab");
writeFileSync(file, text);
file = path.join(cep, "main.js");
text = readFileSync(file, "utf8");
text = text.replace(
  "function defaultBridgeDirectory() {",
  "function defaultBridgeDirectory() {\n  return " +
    JSON.stringify(path.join(runtime, "mailbox")) +
    ";\n}\nfunction unusedProductionDefaultBridgeDirectory() {",
);
text = text.replaceAll("mcp_bridge_", "premiere_agent_lab_");
// The lab is fixed to its own mailbox even if an editor types a different path.
text = text.replaceAll(
  'document.getElementById("tempDir").value.trim()',
  JSON.stringify(path.join(runtime, "mailbox")),
);
text = text.replace(/tempDir = saved;/g, "tempDir = defaultBridgeDirectory();");
text +=
  '\n// Lab installations are pinned; never invoke the production updater.\nhandleUpdateClick = function(){ log(\"Updates disabled in isolated lab\", \"err\"); };\n';
writeFileSync(file, text);
file = path.join(uxp, "manifest.json");
const manifest = JSON.parse(readFileSync(file, "utf8"));
manifest.id = "com.premiereagent.lab.uxp";
manifest.name = "Premiere Agent Lab";
manifest.entrypoints[0].label.default = "Premiere Agent Lab";
manifest.host.minVersion = "26.3.0";
writeFileSync(file, JSON.stringify(manifest, null, 2));
file = path.join(uxp, "index.html");
text = readFileSync(file, "utf8");
text = text.replace(
  '<script src="index.cjs"></script>',
  '<script src="lab-guard.cjs"></script>\n<script src="index.cjs"></script>',
);
if (!text.includes("lab-guard.cjs"))
  throw new Error("UXP guard script insertion failed");
text = text.replaceAll(
  "ws://127.0.0.1:7777/uxp",
  `ws://127.0.0.1:${config.port}/lab-uxp`,
);
writeFileSync(file, text);
file = path.join(uxp, "index.cjs");
text = readFileSync(file, "utf8").replaceAll(
  "premiere-mcp.bridge-session",
  "premiere-agent-lab.bridge-session",
);
text = text.replace(
  "  restoreBridgeSession();",
  '  restoreBridgeSession();\n  document.getElementById("bridge-token").value = ' +
    JSON.stringify(config.token) +
    ';\n  document.getElementById("bridge-url").value = ' +
    JSON.stringify(`ws://127.0.0.1:${config.port}/lab-uxp`) +
    ";",
);
// Serialize all panel requests. Native handlers keep their own lockedAccess transactions.
text = text.replace(
  "  socket.onmessage = (event) => dispatch(event.data);",
  "  let labQueue = Promise.resolve();\n  socket.onmessage = (event) => { labQueue = labQueue.then(() => dispatch(event.data)); };",
);
writeFileSync(file, text);
chmodSync(file, 0o600);
chmodSync(packages, 0o700);
const node = readFileSync(path.join(root, "lab/node-path.txt"), "utf8").trim();
writeFileSync(
  path.join(root, "lab/client-config.json"),
  JSON.stringify(
    {
      mcpServers: {
        "premiere-agent-lab": {
          command: node,
          args: [path.join(root, "dist/lab/index.js")],
        },
      },
    },
    null,
    2,
  ) + "\n",
);
writeFileSync(
  path.join(root, "lab/codex-config.toml"),
  '[mcp_servers."premiere-agent-lab"]\ncommand = ' +
    JSON.stringify(node) +
    "\nargs = " +
    JSON.stringify([path.join(root, "dist/lab/index.js")]) +
    "\n",
  { mode: 0o600 },
);

console.log(
  "Prepared isolated CEP and UXP packages; production installation and Codex configuration unchanged.",
);

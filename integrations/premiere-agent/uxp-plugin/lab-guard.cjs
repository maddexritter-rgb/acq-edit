(function (root) {
  "use strict";
  // This is loaded by the isolated lab package only. Upstream per-operation native
  // lockedAccess/executeTransaction guards remain in force after this preflight.
  async function check(ppro, cmd, guard) {
    if (!guard) return; // read-only invocation; the authenticated server classifies authority
    if (
      typeof guard.projectPath !== "string" ||
      typeof guard.operationId !== "string"
    )
      throw new Error("LAB_INVALID_GUARD");
    const project = await ppro.Project.getActiveProject();
    if (!project || project.path !== guard.projectPath)
      throw new Error("LAB_TARGET_CHANGED");
    const sequence = await project.getActiveSequence();
    const id = sequence ? String(sequence.guid) : null;
    if (id !== guard.sequenceId) throw new Error("LAB_SEQUENCE_CHANGED");
    // Reject argument-level alternate project targets as well as active-target changes.
    for (const key of ["project_path", "projectPath"]) {
      if (cmd.args[key] && cmd.args[key] !== guard.projectPath)
        throw new Error("LAB_ARGUMENT_TARGET_CHANGED");
    }
  }
  root.PremiereAgentLabGuard = { check };
  if (typeof module === "object") module.exports = { check };
})(typeof globalThis !== "undefined" ? globalThis : this);

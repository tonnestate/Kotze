"""No-network regression for manifest-pinned SKILL arm integration."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import gemma_worker as gm
import repair_pipeline as pipeline


class PinnedSkillPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.trusted = Path(self.tmp.name) / "trusted"
        self.trusted.mkdir(mode=0o700)
        self.skill = self.trusted / "verified-skill.txt"
        self.skill.write_text("Inspect the source, localize the defect, and test a minimal fix.")
        self.skill.chmod(0o600)
        self.config = {"trusted": self.trusted, "skill_file": self.skill}
        self.study = {"study_id": "study-1",
                      "skill_sha256": gm.digest(gm.read_prompt(self.skill))}

    def test_skill_is_enabled_only_with_frozen_manifest_digest(self):
        self.assertEqual(
            pipeline.resolve_pinned_skill(self.config, self.study, "SKILL"), self.skill
        )

    def test_base_cannot_accidentally_load_skill(self):
        with self.assertRaisesRegex(pipeline.PipelineError, "BASE arm"):
            pipeline.resolve_pinned_skill(self.config, self.study, "BASE")
        self.assertIsNone(
            pipeline.resolve_pinned_skill({"trusted": self.trusted}, self.study, "BASE")
        )

    def test_stale_or_missing_study_digest_is_blocked(self):
        with self.assertRaisesRegex(pipeline.PipelineError, "manifest digest"):
            pipeline.resolve_pinned_skill(self.config, {"skill_sha256": "0" * 64}, "SKILL")
        with self.assertRaisesRegex(pipeline.PipelineError, "manifest digest"):
            pipeline.resolve_pinned_skill(self.config, {}, "SKILL")
        self.skill.write_text("A different procedure")
        with self.assertRaisesRegex(pipeline.PipelineError, "manifest digest"):
            pipeline.resolve_pinned_skill(self.config, self.study, "SKILL")

    def test_non_private_and_symlinked_files_are_refused(self):
        self.skill.chmod(0o644)
        with self.assertRaisesRegex(pipeline.PipelineError, "private host-owned"):
            pipeline.resolve_pinned_skill(self.config, self.study, "SKILL")
        self.skill.chmod(0o600)
        link = self.trusted / "alias.txt"
        link.symlink_to(self.skill)
        with self.assertRaisesRegex(pipeline.PipelineError, "canonical"):
            pipeline.resolve_pinned_skill(
                {**self.config, "skill_file": link}, self.study, "SKILL"
            )

    def test_missing_skill_does_not_start_skill_arm(self):
        with self.assertRaisesRegex(pipeline.PipelineError, "requires a pinned"):
            pipeline.resolve_pinned_skill({"trusted": self.trusted}, self.study, "SKILL")
        with self.assertRaisesRegex(pipeline.PipelineError, "Unsupported"):
            pipeline.resolve_pinned_skill(self.config, self.study, "EXPERIMENT")


if __name__ == "__main__":
    unittest.main()

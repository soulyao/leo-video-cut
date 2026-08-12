import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def read_reference(name):
    return (REPO_ROOT / "references" / name).read_text(encoding="utf-8")


class ReferencesContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = read_reference("workflow.md")
        cls.production = read_reference("local-production.md")
        cls.quality = read_reference("quality.md")
        cls.all_text = "\n".join((cls.workflow, cls.production, cls.quality))

    def test_workflow_routes_text_images_video_and_mixed_inputs(self):
        for term in (
            "文字",
            "图片",
            "推拉",
            "平移",
            "景深",
            "视差",
            "原视频",
            "本地转录",
            "语义",
            "音频边界",
            "停顿",
            "废话",
            "失败重拍",
            "黑帧",
            "爆音",
            "混合",
            "原视频为主体",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.workflow)

    def test_cover_standard_prioritizes_user_assets_and_checks_each_candidate(self):
        for term in (
            "人物",
            "产品",
            "品牌",
            "视觉参考",
            "ImageGen",
            "原创",
            "标题可读",
            "UI 安全区",
            "人物和产品完整",
            "视频风格一致",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.all_text)

    def test_script_and_storyboard_are_timed_and_production_complete(self):
        for term in (
            "时间",
            "旁白",
            "字幕",
            "画面",
            "素材来源",
            "生成方式",
            "动效",
            "音效",
            "hook",
            "core",
            "CTA",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.all_text)

    def test_local_production_covers_broll_mix_subtitles_and_decode(self):
        for term in (
            "B-roll",
            "背景",
            "插图",
            "BGM",
            "SFX",
            "voice-first",
            "ducking",
            "loudness normalize",
            "错字",
            "断句",
            "布局",
            "ffmpeg -v error",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.production)

    def test_quality_covers_visual_audio_subtitles_hyperframes_and_diagnostics(self):
        for term in (
            "主体裁切",
            "切点爆音",
            "黑帧",
            "字幕",
            "HyperFrames lint",
            "HyperFrames validate",
            "HyperFrames inspect",
            "3 repair rounds",
            "诊断",
            "可复现命令",
            "来源",
            "版权",
            "ffmpeg -v error",
            "解码",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.quality)

    def test_delivery_lists_final_editable_raw_and_unselected_assets(self):
        for term in (
            "output/final-vertical.mp4",
            "output/cover.png",
            "output/subtitles.srt",
            "SRT",
            "HyperFrames",
            "FFmpeg",
            "raw intermediate",
            "two unselected covers",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.all_text)

    def test_final_workflow_safeguards_confirmed_work_titles_cover_and_identity(self):
        for term in (
            "不得重生成已确认",
            "除非用户主动要求",
            "平台",
            "不过度标题党",
            "压缩",
            "拆成系列",
            "真人身份",
            "面部特征",
            "单独明确授权",
            "selected.png",
            "output/cover.png",
            "校验 bytes",
        ):
            with self.subTest(term=term):
                self.assertIn(term, self.all_text)


if __name__ == "__main__":
    unittest.main()

## Description: <br>
Text To Video Hunyuan helps users generate and export 1080p MP4 video clips from text prompts using a remote HunyuanVideo and NemoVideo cloud rendering workflow. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[mory128](https://clawhub.ai/user/mory128) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
External users and creators use this skill to turn text prompts into short AI-generated videos, check credits, preview timeline state, upload source media, and export MP4 results through a cloud rendering service. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Prompts, uploaded media, URLs, timeline state, and export requests are sent to the NemoVideo cloud service. <br>
Mitigation: Use the skill only with media and prompts that may be processed by that provider; avoid confidential, regulated, or consent-sensitive content unless the provider is approved for that use. <br>
Risk: The NEMO_TOKEN credential enables cloud sessions and should not be exposed. <br>
Mitigation: Keep NEMO_TOKEN private, do not display raw token values or API responses, and rotate or re-authenticate when a token expires or may have been exposed. <br>
Risk: Cloud render jobs consume credits and may continue independently of the local session. <br>
Mitigation: Monitor credits and render job status during use, and confirm export readiness before sharing generated download links. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/mory128/text-to-video-hunyuan) <br>
- [NemoVideo cloud service endpoint](https://mega-api-prod.nemovideo.ai) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, API calls, files, guidance] <br>
**Output Format:** [Markdown guidance with API-backed status updates, timeline summaries, export links, and MP4 video outputs] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Remote rendering can return 1080p MP4 exports; prompts, uploads, timeline state, and export requests are sent to NemoVideo.] <br>

## Skill Version(s): <br>
1.0.0 (source: frontmatter and server release evidence) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>

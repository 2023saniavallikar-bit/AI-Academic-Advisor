# Phase #11: Synthetic Media, Copyright and Legal Analysis

**Project:** AI Academic Advisor (Flask, Google Gemini API free tier, RAG over the Vidyashilp University Student Handbook and SOPs, Chroma vector DB)
**Course:** DATA308 Generative AI, Vidyashilp University, Bengaluru
**Status of sources:** checked November 2026. Laws, platform terms and court cases in this area change often. Every source is linked inline, and items marked *(verify before relying)* should be re-checked against the primary text before anyone acts on them.

---

## 1. Scope and method

This section looks at the AI-generated and synthetic outputs our system produces, and asks five questions about each one: who holds the **copyright** (if anyone), who **owns** the output and its inputs, how it should be **attributed**, how it can be **licensed**, and how it could be **misused**.

Method:

1. We listed every place in the project where a model, an API or our own code produces content a user sees or that could leave the system (Section 2).
2. For each output we traced the inputs (university documents, student data, third-party voices and models) and the terms governing each tool.
3. We checked the outputs against Indian law first (Copyright Act 1957, Trade Marks Act 1999, Bharatiya Nyaya Sanhita 2023, Digital Personal Data Protection Act 2023, IT Rules), since the system is built and used in Bengaluru. We added US and EU positions for comparison, along with Google's own terms.
4. We turned the findings into a checklist of practices (Section 6), marking which ones are already implemented and which are recommended.

---

## 2. Inventory of AI-generated outputs

| # | Output | Model / tool | Inputs | Who owns the inputs | Who owns the output | Licence we apply | Main misuse risk | Mitigation |
|---|---|---|---|---|---|---|---|---|
| 1 | Text advising answers | Gemini 2.5 Flash / Flash-Lite via API, gemini-embedding-001 for retrieval | Student question; retrieved chunks of Handbook (Aug 2026), SOPs, curriculum sheets | University (handbook, SOPs, curriculum); student (question) | Unsettled. Google does not claim ownership; the user who prompts is the likeliest "author" under Indian s.2(d)(vi); quoted handbook text stays the university's | None of our own on the quoted parts. Answers shown for personal advising use only | Being treated as official advice; hallucinated rules; copying large handbook extracts | Citations to section/page, "AI-generated, not official advice" label, short quotes only |
| 2 | Spoken answers (TTS) and voice input (STT) | Browser Web Speech API: `speechSynthesis` (OS/browser voices from Google, Microsoft, Apple) and `SpeechRecognition` (in Chrome, server-side at Google) | Text answer; student's voice | Voice models: OS/browser vendor; voice audio: student | Audio is rendered on the fly and not stored; the voice itself stays under the vendor's licence | Not redistributed | Synthetic voice impersonating a Dean or advisor; voice data reaching Google without notice | Stock voices only, no cloning; "AI voice" label; voice input opt-in with privacy notice |
| 3a | Prerequisite-chain diagram / infographic (SVG) | Our own deterministic Python code | Curriculum CSV | University (curriculum data) | Our team (code and layout); the facts in it are not ownable | Code MIT; diagram carries "Source: VU curriculum" | Becoming outdated; mistaken for an official chart | Generated date and source note on every SVG |
| 3b | Optional AI-image infographic (comparison only) | Image-generation model (e.g. Gemini image model) | Text prompt describing the curriculum | Our prompt | Weak or no copyright (little human authorship); Google claims no ownership | CC BY 4.0 for the prompt and notes; image marked "AI-generated" | Garbled or invented course codes; looks authoritative | Kept out of the advising flow; SynthID present; visible AI label |
| 4 | Synthetic transcripts and registration forms (PDF/PNG) | Our code plus Gemini to fill text | Fake names, fake grades, university name and layout | University (name, logo, form design) | Our team (data); university keeps its trade mark | CC BY 4.0 for data only; logo excluded | Forgery: passing a fake as a real record | Diagonal "SYNTHETIC – NOT A REAL RECORD" watermark, no real signatures or seals, metadata tag |
| 5 | Synthetic student profiles (JSON) and synthetic voice query clips | Gemini / our scripts; browser or OS TTS for clips | Prompt templates, random seeds | Our team | Our team (to the extent protectable) | CC BY 4.0 with "synthetic" notice | Re-identification if built from real students; clips used as fake voice evidence | Built from scratch with no real student data; clips use stock voices and are labelled in the filename and metadata |

---

## 3. Detailed analysis per output

### 3.1 Text advising answers (Gemini + RAG)

**Copyright and authorship.** Under the Indian Copyright Act 1957, s.2(d)(vi), the "author" of a computer-generated literary or artistic work is "the person who causes the work to be created". The Act does not say whether that person is the developer, the operator or the user who typed the prompt. Section 17 makes the author the first owner, subject to exceptions such as works made in the course of employment. India has not settled whether a purely AI-generated answer has enough human originality to be protected at all. The RAGHAV episode shows this: the Copyright Office registered the painting *Suryast* in 2020 with the AI tool RAGHAV listed as co-author with Ankit Sahni, and then issued a withdrawal notice asking about the AI's legal status ([Managing IP](https://managingip.com/article/b1vvyqphyskcrg/exclusive-indian-copyright-office-issues-withdrawal-notice-to-ai-co-author); [SpicyIP](https://spicyip.com/2022/10/ai-art-and-indian-copyright-registration.html)). The registration's final status is still unclear *(verify before relying)*.

For comparison, the US is clearer. The D.C. Circuit in *Thaler v. Perlmutter* (18 March 2025) held that copyright requires a human author ([Reed Smith](https://www.reedsmith.com/our-insights/blogs/viewpoints/102k53m/dc-circuit-affirms-ai-cannot-be-author-under-copyright-act/)). The US Copyright Office's *Copyright and AI, Part 2: Copyrightability* (January 2025) says prompts alone are generally not enough, while human selection, arrangement and modification can be protected ([DLA Piper summary](https://dlapiper.com/en-us/insights/publications/2025/03/copyrightability-of-genai-outputs-in-the-us-key-developments)). One report says the US Supreme Court denied certiorari in March 2026 *(verify before relying)*.

**Ownership under Google's terms.** The Gemini API Additional Terms say Google does not claim ownership of generated content, while warning that similar content may be generated for other users. The user is responsible for how the output is used ([Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms)). The bigger issue for us is **data use**. On the unpaid tier, Google may use prompts and responses "to provide, improve, and develop Google products", and human reviewers may read and annotate them. Google tells developers not to submit sensitive, confidential or personal information to unpaid services. Paid (billing-enabled) use is excluded from product improvement ([Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms); [Nov 2025 archive](https://ai.google.dev/gemini-api/terms-archive/terms_11_20_25)). Because our prototype runs on the free tier, **every question a student types, and every handbook chunk we send, may be seen by Google reviewers**.

**Derivative content.** Answers quote and paraphrase the Student Handbook and SOPs. Vidyashilp is a private university, so these documents are most likely the university's copyright under s.17. Short quotations for advising students of the same university sit comfortably within the purpose the documents were written for. Section 52 (fair dealing for private use, research, criticism and review, and reproduction "in the course of instruction") gives further cover for a course project. It is not a licence to republish the handbook as a public dataset.

**Attribution.** Each answer cites the handbook section and page it relied on, and carries an "AI-generated" label.

**Misuse.** The main risk is that a student treats a hallucinated or outdated answer as an official ruling, for example on attendance, grade appeals or credit limits. Google's Prohibited Use Policy also bars "misleading claims of expertise or capability in sensitive areas" and misrepresenting the provenance of generated content ([Google GenAI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy)). Presenting the bot as the university's official voice would put us close to that line.

### 3.2 Spoken audio answers and voice input (Web Speech API)

**Ownership and licensing.** We do not create or own any voice model. `speechSynthesis` uses voices installed in the user's operating system or browser (for example Google, Microsoft or Apple voices). Those voices are licensed by their vendors for use on the device, usually with limits on extracting or redistributing recordings. Playing an answer aloud in the browser is the intended use. Recording those voices and publishing them as a dataset may not be, so our synthetic voice clips (output 5) are kept for internal testing only and labelled.

**Privacy of speech input.** In Chrome, `SpeechRecognition` sends the raw audio to a Google server for transcription, and only the text comes back to the page. It does not work offline ([Mozilla wiki](https://wiki.mozilla.org/Web_Speech_API_-_Speech_Recognition); [Brave community explanation](https://community.brave.com/t/years-of-brave-failing-google-voice-search-with-no-internet-connection-error/395749/2)). *(Verify against current Chrome privacy documentation.)* A voice recording is personal data under the DPDP Act 2023. The DPDP Rules 2025 were notified in November 2025 and most operational obligations phase in by about May 2027 ([SCC Online](https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/); [AMSS](https://www.amsshardul.com/insight/enforcement-of-the-dpdp-act-and-notification-of-the-dpdp-rules/)). A production deployment would need a clear notice and consent before the microphone is used.

**Misuse: voice impersonation.** Synthetic voices can be used to impersonate a Dean, Program Chair or advisor ("this is the Registrar; your registration is cancelled"). Indian courts now protect voice as part of personality rights. The Bombay High Court in *Arijit Singh v. Codible Ventures LLP* (26 July 2024) restrained AI tools from cloning the singer's voice without consent ([SpicyIP](https://spicyip.com/2024/08/synthetic-singers-and-voice-theft-bomhc-protects-arijit-singhs-personality-rights-part-i.html); [Bar & Bench](https://www.barandbench.com/news/bombay-high-court-interim-relief-arijit-singh-personality-rights)), after the Delhi High Court's September 2023 interim order protecting Anil Kapoor's name, voice and likeness ([MediaNama](https://www.medianama.com/2024/08/223-bombay-hc-orders-ai-platforms-to-remove-unauthorized-use-of-arijit-singhs-voice/)). These cases involve celebrities, but the principle (no commercial use of a recognisable person's voice without consent) is a sound rule for faculty and staff too. Impersonation to deceive is also prohibited by Google's policy and can be an offence under IT Act s.66D (cheating by personation using a computer resource). Our system therefore **never clones a real person's voice** and only uses generic stock voices.

### 3.3 Prerequisite-chain diagram: deterministic SVG vs AI image

**(a) Deterministic SVG.** The diagram is drawn by our own Python code from the university's curriculum CSV. The underlying facts (course X requires course Y) are not protected by copyright, since copyright protects expression, not facts. The curriculum sheet as a compilation is the university's. Our code and visual layout are our own work, written by human students, so ordinary copyright applies with the team as authors. There is no AI authorship question. The diagram is reproducible and auditable: the same CSV always gives the same picture.

**(b) AI-image infographic (comparison only).** We generate an infographic with an image model from a text prompt and compare it with (a). **[TO FILL AFTER THE EXPERIMENT: count of wrong/misspelt course codes and non-existent arrows found when checked against courses.csv.]** The expected risk, typical of image models rendering text, is a polished image with invented or misspelt codes. On ownership, the human contribution is only the prompt, so under the US Copyright Office's view it would likely have no copyright, and under Indian s.2(d)(vi) the position is uncertain. Images from Google's image models carry an invisible **SynthID** watermark, and the C2PA "Content Credentials" standard can attach signed provenance metadata. Under the EU AI Act Art. 50, applying from 2 August 2026, providers must mark synthetic images in a machine-readable way and deployers must disclose deepfakes ([artificialintelligenceact.eu](https://artificialintelligenceact.eu/transparency-rules-article-50/); [Baker McKenzie](https://connectontech.bakermckenzie.com/new-eu-guidance-on-ai-transparency-what-should-companies-be-doing-from-2-august-2026)). India's IT Rules amendment of February 2026 requires intermediaries to label "synthetically generated information" (audio, visual and audio-visual) prominently ([Hogan Lovells](https://www.hoganlovells.com/en/publications/india-introduces-mandatory-labelling-for-ai-and-3hour-takedown-for-illegal-content); [SS Rana](https://ssrana.in/articles/india-tightens-oversight-on-ai-generated-content-under-it-rules/)) *(verify before relying; a further draft on continuous labels was open for comment in 2026)*. We are not an intermediary, but labelling is good practice that matches these rules. **Decision:** only the deterministic SVG is used in the advisor; the AI image stays in the report as a labelled example of why it should not be.

### 3.4 Synthetic student records (fake transcripts and registration forms)

**Why they exist.** We need test documents to exercise the transcript-reading feature (Gemini vision) without uploading any real student's records.

**Trade mark and passing off.** The university's name and logo (`vu-logo.png`) are its marks. Under the Trade Marks Act 1999 (s.29 infringement, plus common-law passing off), using them on documents that look official could mislead people about their source. Inside a course project, with the university's knowledge, this is low risk, but the permission should be written down (Section 4).

**Forgery risk.** A realistic fake transcript bearing the university's name is exactly the kind of document that can be used to cheat an employer or another university. The Bharatiya Nyaya Sanhita 2023, which replaced the IPC from 1 July 2024, makes it an offence to make a false document or electronic record (s.335) and to commit forgery (s.336). Higher penalties apply where forgery is for cheating, and possessing or using a forged document as genuine is covered by later sections ([Hyperverge summary](https://hyperverge.co/blog/forgery-laws-punishment/); [lawx.in, BNS Ch. XVIII](https://lawx.in/acts/chapter/855)) *(verify subsection numbering against the gazette text)*. Forgery needs intent to deceive or cause harm, and we have none, but we must make it impossible for someone else to take our files and use them that way.

**Mitigations in place.** Every synthetic record carries a large diagonal **"SYNTHETIC – NOT A REAL RECORD"** watermark across the page, does not include the real Registrar's signature or seal, uses obviously fictional names and IDs (e.g. prefix `SYN-`), and has a metadata field (`Producer: AI Academic Advisor – synthetic test data`). Files are kept in a `synthetic/` folder and not published at high resolution.

### 3.5 Synthetic student profiles (JSON) and synthetic voice query clips

**Ownership and licence.** The profiles are generated from templates and random seeds, with Gemini filling in free-text fields. Our selection and structure of the dataset is human work, so we can licence it. We release it under **CC BY 4.0**, with a notice that all records are synthetic and do not describe real people. Creative Commons licences only work for rights the licensor actually holds, so the licence notice covers our arrangement and code, not any university material.

**Privacy.** Because no real student record was used as a seed, the DPDP Act does not apply to the dataset itself. If profiles were ever "inspired by" real students, rare combinations (a particular minor, CGPA and backlog pattern) could re-identify a person, so this practice is ruled out.

**Voice clips.** Test clips are made with stock TTS voices, not any team member's or staff member's voice. If a team member records their own voice for testing, they give written consent and the clips are deleted after testing.

---

## 4. Rights and permissions by type of material

| Material | Who holds rights | What we may do | Permission needed |
|---|---|---|---|
| **University material**: Student Handbook (Aug 2026), SOPs, curriculum sheets, logo, campus photos | Vidyashilp University (copyright under s.17 for staff-authored documents; trade mark in name/logo; photos owned by the photographer or university) | Use internally for the DATA308 project, which is how the documents were supplied; quote short extracts with citation | Written permission from the university (e.g. Program Chair or Registrar) before public deployment, public GitHub release of the PDFs or embeddings, or any use of the logo outside the course. Check photo credits before reuse |
| **Third-party copyrighted content**: textbooks, websites, fonts, icons, OS voices | The respective authors and vendors | Rely on s.52 fair dealing for instruction, research and review in limited amounts; use fonts and icons under their stated licences | Do not ingest whole textbooks into the RAG index; keep licence files for fonts and icon sets; do not redistribute OS voice recordings |
| **Student-created content**: questions, uploaded transcripts, voice, code and reports written by team members | The student (copyright in their own writing and code; their personal data under DPDP); moral rights to attribution and integrity under s.57 | Process to answer the student's own query | Clear notice and consent before uploads or microphone use; credit team members by name in the report; get consent before reusing another student's work or voice |
| **AI-generated content**: Gemini text, AI images, synthetic data | Unsettled in India (s.2(d)(vi)); no copyright without human authorship in the US; Google claims no ownership | Use, edit and licence our human-arranged outputs; label as AI-generated | Follow Google's Terms and Prohibited Use Policy; disclose AI use in coursework as the university's academic integrity rules require |

---

## 5. Ethical considerations

- **Official-advice confusion.** The largest real-world risk is not copyright but a student acting on a wrong answer about attendance, credits or deadlines. The interface must make clear that the advisor is a study aid and that the Faculty Advisor or Program Chair is the authority.
- **Over-reliance.** Fluent answers invite trust. Showing the source passage beside each answer lets students check it, and the system says "I don't know – please ask your advisor" when retrieval finds nothing relevant, instead of guessing.
- **Bias and fairness.** Gemini may give different tones or recommendations depending on how a question is phrased, or on the name in a profile. We tested the synthetic profiles across names and genders to look for differences in advice.
- **Transparency.** Users should always know when they are reading or hearing AI output. The text label, "AI voice" note and image watermarks serve this purpose, in line with EU AI Act Art. 50 and India's 2026 SGI labelling rules.
- **Privacy and power imbalance.** Students may feel they must use a tool provided by their university. On a free tier where Google may review data, they should be told plainly not to type personal or sensitive details.
- **Dual use of synthetic records.** Realistic fake transcripts help testing but could help fraud. Watermarking and restricted distribution keep the benefit while reducing the harm.

---

## 6. Practices for our system (checklist)

**Implemented in the prototype**

- [x] "AI-generated – may be inaccurate" label on every chat answer, and an "AI voice" note when audio plays.
- [x] Citations (document, section, page) under every answer, built from the retrieved chunks.
- [x] Fixed disclaimer: *"This is not official academic advice. Please confirm with your Faculty Advisor or Program Chair before acting."*
- [x] "I don't know – please ask your advisor" fallback when retrieval confidence is low.
- [x] Prerequisite diagrams drawn by deterministic code from the curriculum CSV, with source and date shown; AI images not used for advising.
- [x] "SYNTHETIC – NOT A REAL RECORD" watermark, fictional `SYN-` IDs and no real signatures or seals on all fake transcripts and forms.
- [x] Only stock browser or OS voices; **no voice cloning** of any real person.
- [x] Synthetic profiles built without any real student data.

**Recommended before any wider deployment**

- [ ] **Do not send real student data to the free-tier API.** Use only synthetic transcripts for testing; for real use, move to a billing-enabled (paid) Gemini project, whose data is not used for product improvement, or a university-approved provider.
- [ ] Get **written permission from the university** to use the handbook, SOPs, curriculum data, logo and campus photos in a deployed or public version.
- [ ] Add a privacy notice and opt-in toggle before microphone use, explaining that Chrome sends audio to Google for transcription; offer typed input as the default.
- [ ] Add provenance metadata to exported files: XMP/PDF metadata on synthetic records, and C2PA Content Credentials for any images; keep SynthID marks intact on Google-generated images.
- [ ] **Licensing:** release our code under the **MIT License** and the synthetic dataset and diagrams under **CC BY 4.0**, with a NOTICE file stating that university documents, logo and photos are **excluded** and remain the university's property, and that all records are synthetic.
- [ ] **Retention:** do not store chat logs or audio by default; if logs are kept for evaluation, strip identifiers, keep them for no more than one semester, and delete uploaded transcripts right after processing.
- [ ] Re-check the Gemini API Terms, Google's Prohibited Use Policy and the DPDP Rules timetable each semester, since all three change.
- [ ] Ask the university's academic office to review the disclaimer wording and name a human contact for escalations.
- [ ] Credit all team members, and state in the report which parts were AI-assisted, following the university's academic integrity policy.

---

## 7. Limitations

This analysis was written by students for a course assignment. **It is not legal advice.** It relies largely on secondary sources (law-firm notes, legal blogs, news reports) and on platform terms that Google can change at any time. Indian law on AI authorship is unsettled, the DPDP Rules are still being phased in, and the IT Rules on synthetic content were being amended during 2026. Section numbers for the BNS, dates for the EU AI Act marking duty, and the current status of the RAGHAV registration should be checked against primary texts. Any real deployment that handles actual student records, or uses the university's name and marks publicly, should be reviewed by the university's legal or compliance office first.

### Key sources

- Google, Gemini API Additional Terms of Service: https://ai.google.dev/gemini-api/terms
- Google, Generative AI Prohibited Use Policy (last modified 17 Dec 2024): https://policies.google.com/terms/generative-ai/use-policy
- Indian Copyright Act 1957, ss. 2(d)(vi), 17, 52, 57 (India Code): https://www.indiacode.nic.in/handle/123456789/1367
- RAGHAV / *Suryast* withdrawal notice: https://managingip.com/article/b1vvyqphyskcrg/exclusive-indian-copyright-office-issues-withdrawal-notice-to-ai-co-author ; https://spicyip.com/2022/10/ai-art-and-indian-copyright-registration.html
- *Thaler v. Perlmutter* (D.C. Cir. 2025): https://www.reedsmith.com/our-insights/blogs/viewpoints/102k53m/dc-circuit-affirms-ai-cannot-be-author-under-copyright-act/
- US Copyright Office Part 2 report summary: https://dlapiper.com/en-us/insights/publications/2025/03/copyrightability-of-genai-outputs-in-the-us-key-developments
- EU AI Act Article 50 guide: https://artificialintelligenceact.eu/transparency-rules-article-50/
- India IT Rules Amendment 2026 (synthetic content labelling): https://www.hoganlovells.com/en/publications/india-introduces-mandatory-labelling-for-ai-and-3hour-takedown-for-illegal-content
- DPDP Rules 2025: https://www.scconline.com/blog/post/2025/12/26/digital-personal-data-protection-rules-2025-key-highlights/
- BNS 2023 forgery provisions: https://lawx.in/acts/chapter/855 ; https://hyperverge.co/blog/forgery-laws-punishment/
- *Arijit Singh v. Codible Ventures* (Bom HC 2024): https://spicyip.com/2024/08/synthetic-singers-and-voice-theft-bomhc-protects-arijit-singhs-personality-rights-part-i.html
- Web Speech API recognition data flow: https://wiki.mozilla.org/Web_Speech_API_-_Speech_Recognition
- Creative Commons CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- C2PA Content Credentials: https://c2pa.org/ ; Google SynthID: https://deepmind.google/technologies/synthid/

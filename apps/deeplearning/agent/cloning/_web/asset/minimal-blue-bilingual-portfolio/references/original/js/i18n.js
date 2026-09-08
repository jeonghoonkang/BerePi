// i18n translations
const translations = {
    en: {
        'nav.about': 'About',
        'nav.portfolio': 'Portfolio',
        'nav.more': 'More',
        'nav.experience': 'Experience',
        'nav.projects': 'Projects',
        'nav.publications': 'Publications',
        'nav.teaching': 'Teaching',
        'nav.ecosystem': 'Codex & DevX',
        'nav.ebook': 'E-book',
        'nav.media': 'Media',
        'nav.life': 'Life',
        'nav.contact': 'Contact',

        // Site
        'site.name': 'Seowoo Han',
        'meta.title': 'Seowoo Han | Applied AI Engineer · AX Educator · Codex Ambassador',
        'meta.description': 'Portfolio of Seowoo Han: applied AI and computer-vision products, AX education, OpenAI Codex Ambassador work, projects, writing, press, and talks.',

        // Hero
        'hero.name': 'Seowoo Han',
        'hero.greeting': "Hello, I'm",
        'hero.title': 'Applied AI Engineer · AX Educator · Developer Experience',
        'hero.education': 'Ph.D. Candidate, Korea University CS | CMU AI Program (Full Scholarship by IITP, Korea)',
        'hero.description': 'I connect applied AI and computer vision to real products and operations. Through AX education and my work as an OpenAI Codex Ambassador, I design workflows people can test, review, and reuse in their own work.',
        'hero.cta': 'Get in Touch',
        'hero.projects': 'View Projects',
        'hero.codexWork': 'View Codex Work',
        'hero.codex101': 'Codex 101',
        'hero.portfolio': 'View selected work',
        'hero.links': 'Links',

        // Portfolio overview
        'portfolio.kicker': 'Selected portfolio',
        'portfolio.title': 'Connecting technology to products, work, and learning experiences',
        'portfolio.intro': 'Engineering, AX education, Codex community work, and public content are connected through the roles I took and the work people can verify.',
        'portfolio.engineering.eyebrow': 'Engineering',
        'portfolio.engineering.title': 'Applied AI engineering for products and operations',
        'portfolio.engineering.desc': 'I design inputs, exceptions, and review steps so drone imagery, OCR, object detection, and multimodal data work inside real user flows.',
        'portfolio.engineering.cta': 'View experience and projects →',
        'portfolio.codex.eyebrow': 'Codex & DevX',
        'portfolio.codex.title': 'Codex 101 and practical developer workflows',
        'portfolio.codex.desc': 'I create Korean and English guides, demos, and onboarding resources that connect new capabilities to real development work.',
        'portfolio.codex.cta': 'Open Codex 101 ↗',
        'portfolio.ax.eyebrow': 'AX & Education',
        'portfolio.ax.title': 'AX education that changes one real workflow',
        'portfolio.ax.desc': 'My workshops focus on problem definition, execution, human review, and iteration instead of feature walkthroughs.',
        'portfolio.ax.cta': 'View the AX Skillathon recap ↗',
        'portfolio.community.eyebrow': 'Community',
        'portfolio.community.title': 'Communities where one person’s work becomes another’s next experiment',
        'portfolio.community.desc': 'Through Workflow Show & Tell and Codex workshops, I gather cases, connect people and programs, and publish the outcomes.',
        'portfolio.community.cta': 'View the results page ↗',

        // About
        'about.title': 'About Me',
        'about.intro': 'I\'m an <strong>AI Engineer & Developer Experience</strong> builder. I build practical AI systems, developer workflows, and learning resources that help people turn new AI capabilities into useful products.',
        'about.education.korea': '🎓 Korea University, Ph.D. in Computer Science (ABD)',
        'about.education.cmu': '🇺🇸 Carnegie Mellon University AI Intensive Program (Full IITP National Scholarship, Top 31 Nationwide)',
        'about.education.combined': 'Korea Univ. Ph.D. in CS · <span class="edu-secondary">CMU AI Program</span>',
        'about.skills': 'Tech Stack',
        'about.education': 'Education',
        'about.edu.korea': 'Ph.D. Candidate in Computer Science (ABD)',
        'about.edu.cmu': 'Intensive AI Program (IITP Full Scholarship, Top 31 Nationwide)',
        'about.edu.khu.ms': 'M.S. in Electronic Engineering',
        'about.edu.khu.bs': 'B.S. in Electronic Engineering, Summa Cum Laude',

        // Experience
        'experience.title': 'Experience',
        'exp.bgarage.narrative': "Automated warehouse inventory inspection with drones. Developed vision AI systems to extract label information from drone-captured images in warehouse environments, and now enhancing perception systems for safe autonomous drone navigation. Pushing the boundaries of mono RGB depth estimation.",
        'exp.visit.narrative': 'Led the enhancement of RoundPic, an existing 360° panoramic camera app. With a team of 5 engineers, advanced its AI-based inpainting and stitching algorithms to reduce visible seams in panoramic images, helping grow the customer base 3x in just 2 months.',
        'exp.viewmagine.narrative': 'Directed technical strategy for AI-powered infrastructure inspection. Our VODA system detects building cracks at 0.01mm precision using drone imagery.',
        'exp.keti.company': 'Korea Electronics Technology Institute',
        'exp.keti.narrative': 'Developed real-time traffic monitoring AI for smart city infrastructure. Built detection pipelines using YOLO and DeepSORT, achieving 98% accuracy on multi-CCTV feeds. This research led to 2 international publications.',
        'exp.webarter.narrative': 'Founded a social media startup at CMU targeting U.S. college students. Our mission was breaking filter bubbles by exposing students to diverse perspectives. Built the app with Flutter and ML-powered recommendation systems. The experience taught me how to ship products that people actually use.',
        'exp.cesInterview': 'CES 2023 AVING Interview',
        'exp.linkedinPost': 'LinkedIn Post',
        'exp.githubRepo': 'GitHub Repo',
        'exp.aihubDataset': 'AIHub Dataset',

        // Projects
        'projects.title': 'AI-native Projects',
        'projects.kicker': 'Project archive',
        'projects.portfolioIntro': 'Product work, client work, impact projects, and early experiments are documented with their verified scope and public links.',
        'projects.order.beatpaws': '01 · Codex demo / teaching asset',
        'projects.order.kibbl': '02 · AI product architecture',
        'projects.order.zet': '03 · Agent/client workflow',
        'projects.order.dva': '04 · Production impact work',
        'projects.order.impactbridge': '05 · Impact MVP',
        'projects.order.retext': '06 · Accessibility AI',
        'projects.order.explore': '07 · Archived early experiment',
        'projects.order.findleader': '08 · Archived civic-tech experiment',
        'projects.order.webarter': '09 · Startup/product leadership',
        'projects.beatpaws.title': 'BeatPaws with Codex',
        'projects.beatpaws.desc': 'Built a playable web rhythm game with Codex for Vibe Jam 2026, then turned the build process into a developer-facing talk about iteration loops, playtesting, feedback, and shipping AI-written code as a real product.',
        'projects.impactbridge.title': 'ImpactBridge',
        'projects.impactbridge.desc': 'Platform connecting social innovators with tech talent. Supported by Kakao Impact.',
        'projects.retext.desc': 'AI document summarization for seniors and visually impaired users. Accessibility-first UX.',
        'projects.findleader.title': 'Find My Leader',
        'projects.findleader.desc': 'Archived civic-tech experiment that helped voters compare candidate positions and reached 2,000+ users during the campaign window.',
        'projects.explore.desc': 'Archived early prototype for generating personal-branding sentences, built quickly with React and AWS Lambda.',
        'projects.kibbl.desc': 'Designed an AI-powered food analysis architecture combining computer vision, LLMs, vector search, structured nutrition data, and RESTful APIs.',
        'projects.zet.desc': 'Built AI agent-based creative automation workflows that generated ad strategy, scene structures, visual layouts, and brand-aligned campaign concepts.',
        'projects.techabreak.title': 'Tech a Break',
        'projects.techabreak.desc': "The interview-format Season 1 has concluded. Tech a Break now documents Seowoo Han's thoughts.",
        'projects.dva.desc': 'A 2-year nonprofit collaboration as part of a Tech for Impact pilot cohort. Developed an AI web solution to detect and track tourism boats, protecting the habitat of Jeju\'s Indo-Pacific bottlenose dolphins.',
        'projects.dva.kickoff': 'Kickoff Meeting',
        'projects.dva.journey': 'Project LOG',
        'projects.dva.partnership': 'Tech For Impact MOU',
        'projects.dva.moducon': 'MODUCON Talk',
        'projects.dva.season2': 'Season 2 Start',
        'projects.dva.usertest': 'User Testing',
        'projects.dva.documentary': 'Mini Documentary',
        'projects.dva.media': 'Media & Articles',
        'projects.dva.modulabs': 'Modulabs Blog',
        'projects.dva.brunch': 'Kakao Impact Brunch',
        'projects.badge.kakao': 'Kakao Impact Support',
        'projects.badge.personal': 'Personal',
        'projects.badge.team': 'Team Project',
        'projects.badge.client': 'Client Work',
        'projects.badge.codexDemo': 'Codex Demo',
        'projects.roundpic.desc': '360° panoramic image creation app enhanced with AI-based inpainting and stitching algorithms',
        'projects.voda.desc': 'Drone-based building defect analysis and crack detection system',
        'projects.traffic.title': 'Traffic Analysis',
        'projects.traffic.desc': "Real-time traffic flow analysis using CCTV bird's-eye view conversion",
        'projects.posvision.desc': 'OCR-based parking lot management and license plate recognition system',
        'projects.webarter.desc': 'Co-founded as CTO. Social network for US college students with ML-powered recommender systems.',
        'projects.viewMore': 'Mini Documentary',
        'projects.tryApp': 'Try App',
        'projects.readNewsletter': 'Read Newsletter',
        'projects.devStory': 'Dev Story',
        'projects.experiment': 'Experiment Review',

        'publications.title': 'Publications',
        'publications.intlJournals': 'International Journals',
        'publications.intlConfs': 'International Conferences',
        'publications.domestic': 'Domestic Publications',
        'publications.viewPaper': 'View Paper',

        // Life
        'life.title': 'Life & Hobbies',
        'life.travel.title': 'Travel',
        'life.travel.desc': 'I have traveled to countries including Switzerland, the UK, the Czech Republic, Germany, France, the United States, Thailand, Guam, Japan, China, and South Africa. I enjoy stepping outside familiar surroundings and experiencing different cultures and ways of life.',
        'life.camping.title': 'Camping',
        'life.camping.desc': 'I enjoy spending time in nature, stepping away from screens, and slowing down.',
        'life.nightsky.title': 'Stargazing',
        'life.nightsky.desc': 'I am interested in earth science and enjoy observing the stars, the moon, and how the sky changes with the seasons.',
        'life.coding.title': 'Side Projects',
        'life.coding.desc': 'When an idea comes to mind, I build a small version first and develop it by using it myself.',
        'life.photo.title': 'Photography',
        'life.photo.desc': 'I photograph scenes from trips and everyday life as a way to preserve the moments I care about.',
        'life.books.title': 'Reading',
        'life.books.desc': 'I read across genres, from technology to essays, to discover new perspectives and questions.',

        // Teaching
        'teaching.title': 'Teaching & Education',
        'teaching.intro': 'Sharing knowledge in AI and Computer Vision through various educational platforms.',
        'teaching.cat.instructor': 'Instructor',
        'teaching.cat.mentor': 'Tutor & Mentor',
        'teaching.cat.ambassador': 'Ambassador',
        'teaching.topic.cv': 'Computer Vision',
        'teaching.topic.chatgpt': 'ChatGPT & Generative AI',
        'teaching.topic.ethics': 'AI Ethics',
        'teaching.topic.career': 'AI Career',
        'teaching.topic.programming': 'AI Introduction',
        'teaching.topic.career.mentor': 'Career',
        'teaching.topic.ai_mentoring': 'AI Mentoring',
        'teaching.topic.ocr': 'OCR Challenges',
        'teaching.topic.ds': 'Data Science & AI',
        'teaching.topic.bootcamp': 'AI Bootcamp',
        'teaching.platform.fastcampus': 'FastCampus',
        'teaching.platform.teamsparta': 'TeamSparta / Sparta Coding Club',
        'teaching.platform.modulabs': 'MODULABS',
        'teaching.platform.wantedlab': 'WantedLab',
        'teaching.platform.elice': 'Elice (Alice Coding)',
        'teaching.platform.codeit': 'Codeit',
        'teaching.platform.cv_mentor': 'Likelion, Upstage, Day1Company',
        'teaching.platform.ocr_mentor': 'Upstage, Day1Company',
        'teaching.platform.naver': 'NAVER Connect Foundation',
        'teaching.platform.sparta': 'Sparta Coding Club, Codeit',

        // Talks
        'nav.talks': 'Talks',
        'talks.title': 'Invited Talks',
        'talks.type.panel': 'Panel Talk',
        'talks.beatpaws.title': 'Building BeatPaws with Codex',
        'talks.beatpaws.subtitle': 'Dankook University Tech for !mpact for Campus',
        'talks.beatpaws.desc': 'A one-hour session on building BeatPaws, a web rhythm game made with Codex for Vibe Jam 2026, and how AI-written code becomes a real playable product through small loops, playtesting, feedback, and iteration.',
        'talks.beatpaws.youtube': 'English Lecture Video',
        'talks.iwd.title': "International Women's Day: Female Leadership in AI",
        'talks.iwd.subtitle': 'Canadian & UK Embassies in Seoul',
        'talks.iwd.desc': 'Invited panel speaker for the March 9, 2026 event co-hosted by the Canadian and UK Embassies in Seoul, joined by 35 participants including students and early-career AI professionals.',
        'talks.leadher.subtitle': 'Personal Branding in the AI Era',
        'talks.leadher.desc': 'A talk for 80+ women developers on how personal branding, not job titles, will define our careers in the AI era. Balancing measured skepticism with cautious optimism while actively adapting to change.',
        'talks.aiconf.title': 'AI for Good Conference 2025',
        'talks.aiconf.subtitle': 'Kakao Impact x Social Value Festa',
        'talks.aiconf.desc': 'Presentation on AI for social good and tech for impact initiatives at Kakao Impact x Social Value Festa.',
        'talks.code.subtitle': 'The Secret of Developer Leadership',
        'talks.code.desc': 'A session on balancing "I" and "We" in leadership. Leadership has no fixed formula—everyone leads differently, and followership is just as essential.',
        'talks.modupop.subtitle': 'DVA LAB: Marine Ecosystem AI Monitoring',
        'talks.modupop.desc': 'Vision AI-based drone video analysis web service for Jeju dolphin protection, including ship speed estimation using BEV transformation.',
        'talks.jeju.desc': 'Talk on protecting Indo-Pacific bottlenose dolphins near Jeju using AI-based ship detection and tracking technology.',
        'talks.digilab.subtitle': 'Changing the World with Technology',
        'talks.digilab.desc': 'Presentation on AI-driven conservation efforts for Indo-Pacific bottlenose dolphins, inspired by real-time drone vision systems.',
        'talks.wtm.desc': "Talk on how emerging technologies can shape tomorrow, drawing lessons from DVA LAB's social impact projects.",
        'talks.moducon.desc': 'Presentation on the journey of uniting individual talents to solve social problems through collaborative AI projects, inspired by DVA LAB.',
        'talks.google.desc': 'Founded a social media startup targeting U.S. college students, focused on breaking filter bubbles and encouraging diverse perspectives.',
        'talks.posco.title': 'POSCO E&C Smart Construction Academy',
        'talks.posco.desc': 'Invited lecture on AI applications and positive influence in construction technology.',
        'talks.watchVideo': 'Watch Video',
        'talks.talkReview': 'Talk Review',
        'talks.watchReplay': 'Watch Replay',
        'talks.eventInfo': 'Event Info',

        // Experience
        'exp.interview': 'Interview',
        'exp.viewmagine.narrative': 'Directed technical strategy for AI-powered infrastructure inspection. Our VODA system detects building cracks at 0.01mm precision using drone imagery. Represented the company at CES 2023 in Las Vegas, showcasing our drone-based crack detection technology.',

        // Contact
        'contact.title': 'Get in Touch',
        'contact.text': "I'm always open to discussing new projects, creative ideas, or opportunities to be part of your vision.",

        // Media
        'media.title': 'Media & Archive',

        // Codex & Developer Experience
        'ecosystem.title': 'Codex & Developer Experience',
        'ecosystem.ambassador.desc': 'Helping Korean developers connect Codex to real product work through practical guides, demos, workshops, and feedback loops.',
        'ecosystem.proof.guide.label': 'Guide',
        'ecosystem.proof.guide': 'Created Codex 101, a bilingual Korean/English practical guide for OpenAI Codex workflows, featured in the OpenAI Developers Showcase.',
        'ecosystem.proof.community.label': 'Community',
        'ecosystem.proof.community': "Connected OpenAI Korea with the IT's Study community to plan a practical learning program, while also hosting Codex meetups, demos, workshops, and onboarding sessions for Korean developers and builders.",
        'ecosystem.proof.feedback.label': 'Feedback',
        'ecosystem.proof.feedback': 'Synthesized Korean Codex user feedback from 115 survey responses and 57 open-ended comments into structured DevX insights.',
        'ecosystem.latest.label': 'Latest field notes',
        'ecosystem.latest.date': 'July 2026',
        'ecosystem.latest.roboflow.kicker': 'Roboflow MCP',
        'ecosystem.latest.roboflow.title': 'Fridge expiry-date web app with Codex + Roboflow MCP',
        'ecosystem.latest.roboflow.desc': 'A practical walkthrough of MCP tool discovery, read-only dataset search, safe key handling, and turning computer-vision inference into an app workflow.',
        'ecosystem.latest.onboarding.kicker': 'Codex onboarding',
        'ecosystem.latest.onboarding.title': "Delegate Your Work with the ChatGPT App - Fifth Revised Edition",
        'ecosystem.latest.onboarding.desc': "A free guide to delegating real work with the ChatGPT app. Non-developers can start with Chat or Work, and developers with Codex; their capabilities overlap, so choose the interface that suits your work. The September 5, 2026 fifth revised edition covers GPT-6 Astra, model choices, 21 new screenshots, and ways to continue tasks and review outputs.",
        'ecosystem.latest.workflowShowTell.kicker': 'Workflow Show & Tell Seoul',
        'ecosystem.latest.workflowShowTell.title': '2026 results page',
        'ecosystem.latest.workflowShowTell.desc': 'A public record of the event outcomes, participant workflows, and the community experience around practical AI work.',
        'ecosystem.techabreak.date': 'Season 1 Complete',
        'ecosystem.techabreak.desc': "The interview-format Season 1 has concluded. Tech a Break now documents Seowoo Han's thoughts.",
        'ecosystem.btn.linkedin': '📝 LinkedIn',
        'ecosystem.btn.youtube': '▶️ YouTube',
        'ecosystem.btn.articles': '📰 Articles',
        'ecosystem.btn.lectures': '🎤 Lectures & Talks',
        'ecosystem.btn.events': '🎪 Events',
        'ecosystem.btn.mediaCoverage': '🗞️ Media Coverage',
        'ecosystem.btn.series': '✉️ Series',
        'ecosystem.comingSoon': 'Coming soon',
        'ecosystem.article.codex101': 'Codex 101 - OpenAI Codex Complete Guide',
        'ecosystem.article.aiAgent': 'Understanding AI Agent Concepts',
        'ecosystem.article.codexBestPractices': 'OpenAI Codex Best Practices (Korean Summary)',
        'ecosystem.article.roboflowMcp': 'Codex + Roboflow MCP fridge expiry-date app',
        'ecosystem.article.agentWorkflow': 'Agent Workflow Evolution with OmC, OmX, and Codex',
        'ecosystem.article.dearHumans': "Dear Humans, What AI Still Can't Answer for Us",
        'ecosystem.article.codexSimple': 'Codex, Explained Simply',
        'ecosystem.article.plugins': 'How Plugins Actually Work in Codex',
        'ecosystem.link.codexAnnouncement': 'OpenAI Codex Ambassador announcement',
        'ecosystem.link.meetupRecruitment': 'Codex Community Meetup - Seoul 3.11 (Host Recap)',
        'ecosystem.link.codex101Story': 'Why I built Codex 101',
        'ecosystem.link.aiAgentStory': 'Why I wrote Understanding AI Agent Concepts',
        'ecosystem.link.ralphtonRecap': '2026.02.28-03.01 Ralphton (Field Recap)',
        'ecosystem.link.codexForOpenSource': 'Codex for Open Source program announcement',
        'ecosystem.link.codexWebinar': 'OpenAI webinar: multi-agent workflows with Codex',
        'ecosystem.link.codexImpactRecap': '2026.06.27 Codex Impact Workshop recap',
        'ecosystem.link.workflowShowTellRecap': 'Workflow Show & Tell Seoul 2026 post-event reflection',
        'ecosystem.link.itsStudyPlanning': "IT's Study: OpenAI Korea collaboration and program planning",
        'ecosystem.link.day1AxSkillathon': 'Day1 Company AX Skillathon: Codex and Skill workshop',
        'ecosystem.lecture.day1AxSkillathon': '2026.07.13 Day1 Company AX Skillathon - Codex and Skill Workshop',
        'ecosystem.lecture.companyAxOnboarding': '2026.07.25 Enterprise AX Onboarding at Safety Inspection Company S - Practical Codex Training',
        'ecosystem.lecture.parentsDayAi': "2026.05.08 OpenAI x FastCampus AI Parents' Day - Main Codex Lecture",
        'ecosystem.link.roboflowMcpPost': '2026.06.08 Codex + Roboflow MCP article',
        'ecosystem.link.codexOnboardingPdf': '2026.06 Codex onboarding PDF post',
        'ecosystem.link.techabreak.substack': 'Read Tech a Break',
        'ecosystem.link.techabreak.story': 'Why I started Tech a Break',
        'ecosystem.youtube.plainBusinessmanEp1': '평범한 사업가 Ep. 1 - Codex app basics and the core workflow',
        'ecosystem.youtube.plainBusinessmanEp2': '평범한 사업가 Ep. 2 - Sites, Ultra, Side Chat, and real workflows',
        'ecosystem.link.parentsDayOfficialVideo': "Official OpenAI video: AI Parents' Day",
        'ecosystem.event.meetupHost': '2026.03.11 Codex Community Meetup - Seoul (Solo Host)',
        'ecosystem.event.codexImpactWorkshop': '2026.06.27 Codex Impact Workshop',
        'ecosystem.event.workflowShowTellRecap': '2026.07.13 Workflow Show & Tell Seoul',
        'ecosystem.event.workflowShowTell': '2026 Workflow Show & Tell Seoul — results page',
        'ecosystem.event.ralphtonSponsor': '2026.02.28-03.01 Ralphton (Community Sponsorship)',
        'ecosystem.media.codexImpactVentureSquare': 'Codex Impact Workshop - VentureSquare',
        'ecosystem.media.codexImpactTheButter': 'Codex Impact Workshop - The Butter',
        'ecosystem.media.parentsDayYtnYoutube': '"AI instead of carnations" - YTN video',
        'ecosystem.media.parentsDayNaverTv': '"Building an app with my child using AI" - Naver TV',
        'ecosystem.media.parentsDayYtnArticle': 'ChatGPT and voice commands for seniors - YTN',

        // E-book
        'ebook.label': 'Free PDF',
        'ebook.price': 'Free · $0',
        'ebook.title': "Delegate Your Work with the ChatGPT App - Fifth Revised Edition",
        'ebook.desc': "A free guide to delegating real work with the ChatGPT app. Non-developers can start with Chat or Work, and developers with Codex; their capabilities overlap, so choose the interface that suits your work. The September 5, 2026 fifth revised edition covers GPT-6 Astra, model choices, 21 new screenshots, and ways to continue tasks and review outputs.",
        'ebook.readingNote': 'Do not ask AI to summarize this book for you. Set aside 1-2 hours and read it yourself. It is worth that time.',
        'ebook.previewTitle': 'Inside the book',
        'ebook.preview.item1': "Start in Chat, Work, or Codex to suit your task",
        'ebook.preview.item2': 'Compare local and cloud Work and connect multiple source folders',
        'ebook.preview.item3': "Explore Voice, Pet, the Chrome extension, and Sites",
        'ebook.preview.item4': 'Document work rules with AGENTS.md and memory',
        'ebook.preview.item5': "Manage long tasks and understand Goal and scheduling across environments",
        'ebook.preview.item6': 'Create Skills and systematize repetitive work',
        'ebook.preview.item7': "Adjust from Astra Medium; check usage and reset credits",
        'ebook.preview.item8': "Work output examples, multiple Gmail accounts, and document review checklists",
        'ebook.meta.versionLabel': 'Version',
        'ebook.meta.version': "Fifth revised edition · 2026.09.05",
        'ebook.meta.formatLabel': 'Format',
        'ebook.meta.format': "PDF · 96 pages",
        'ebook.meta.updateLabel': 'Update',
        'ebook.meta.update': "2026.09.05 content revision",
        'ebook.downloadCountLabel': 'Downloads',
        'ebook.downloadCountUnavailable': 'Counting soon',
        'ebook.download': 'Download PDF',
        'ebook.getFreeOnLatpeed': 'View sales page',
        'ebook.all': 'View all e-books',
        'ebook.note': 'Free PDFs can be downloaded directly. For the paid e-book, open its sales page to review the contents and purchase details.',
        'ebook.home.title': 'E-books',
        'ebook.home.desc': 'My e-books range from a career essay about work in the AI era to a practical Codex guide and an IT glossary.',
        'ebook.home.codex.point1': "Choose a starting point in Chat, Work, or Codex",
        'ebook.home.codex.point2': "Start with Astra Medium and explore Voice, Chrome, and Sites",
        'ebook.home.codex.point3': "Connect prior conversations and Gmail accounts; review documents and repeat workflows",
        'ebook.related.pangyo.title': 'Pangyo Dictionary',
        'ebook.related.pangyo.desc': '240 IT, software, and startup terms to skim before vibe coding with AI',
        'ebooks.label': 'Library',
        'ebooks.title': 'E-books',
        'ebooks.desc': 'My e-books range from a career essay about work in the AI era to a practical Codex guide and an IT glossary.',
        'ebooks.portfolioCta': 'Portfolio section',
        'ebooks.detailCta': 'View details',
        'arrow.label': 'Paid e-book',
        'arrow.price': 'KRW 16,900',
        'arrow.title': 'The Harder I Worked, the More I Disappeared',
        'arrow.desc': 'A career essay for the AI era about finding your own standards beyond other people’s expectations and job titles. It also includes questions and a workbook for reinterpreting your own experience.',
        'arrow.readingNote': 'The 100-page PDF includes an 83-page essay and the 17-page My Arrow Map workbook.',
        'arrow.previewTitle': 'Questions from the book',
        'arrow.preview.item1': 'Find strengths through the problems you repeatedly solved',
        'arrow.preview.item2': 'Separate the desire to grow from the urge to prove yourself',
        'arrow.preview.item3': 'Set boundaries around roles, compensation, and endings',
        'arrow.preview.item4': 'Filter feedback through your values and intentions',
        'arrow.preview.item5': 'Choose the smallest experiment for the next 30 days',
        'arrow.meta.version': 'First edition · 2026.07',
        'arrow.meta.format': 'PDF · 100 pages',
        'arrow.meta.includedLabel': 'Included',
        'arrow.meta.included': '17-page workbook',
        'arrow.cta': 'View sales page',
        'arrow.deadline': 'Thanks to your interest, sales have been extended through September 30, 2026.',
        'arrow.closed': 'Sale ended',
        'arrow.closedNote': 'This limited sale has ended.',
        'arrow.externalNote': 'Click to open the Latpeed sales page in a new tab.',
        'pangyo.label': 'Free PDF',
        'pangyo.price': 'Free · $0',
        'pangyo.title': 'Pangyo Dictionary',
        'pangyo.desc': 'A practical IT glossary for non-developers and office workers who have started building with AI. It lightly explains terms like spec, API, deployment, QA, and MVP so you can talk with developers more comfortably.',
        'pangyo.readingNote': 'It helps sentences like "Please confirm the aligned spec ASAP" feel a little less strange.',
        'pangyo.previewTitle': 'Inside the glossary',
        'pangyo.preview.item1': 'Meetings and communication: align, sync, confirm, follow-up, scrum',
        'pangyo.preview.item2': 'Work progress: resource, due date, scope, blocker, ownership',
        'pangyo.preview.item3': 'Development practice: deploy, rollback, QA, code review, API, vibe coding',
        'pangyo.preview.item4': 'Product and data: MVP, PoC, agile, funnel, retention, SQL',
        'pangyo.preview.item5': 'AI and startup terms: LLM, RAG, pitching, valuation, PMF',
        'pangyo.meta.version': '2026.07.02',
        'pangyo.meta.format': 'PDF · 18 pages',
        'pangyo.meta.update': 'Drive file versioned',

        'media.profile.title': 'Wanted Lab People Encyclopedia',
        'media.profile.desc': 'An honest conversation about finding meaning in work, dealing with workplace stress and gaslighting, and the lessons learned along the way.',
        'media.btn.article': 'View Article',
        'media.btn.youtube': 'Watch on YouTube',
        'media.modulabs.title': 'DVA LAB Story',
        'media.modulabs.desc': 'Interview on building "safe greenhouses" for technical experiments and community-led AI projects.',
        'media.plainBusinessmanEp1.title': '평범한 사업가 AI Podcast #87',
        'media.plainBusinessmanEp1.desc': 'An interview covering Codex app basics and the core workflow.',
        'media.plainBusinessmanEp2.title': '평범한 사업가 AI Podcast #92',
        'media.plainBusinessmanEp2.desc': 'An interview connecting Sites, Ultra, and Side Chat in a real workflow.',

        // Partners
        'partner.likelion': 'Likelion',
        'partner.naver': 'NAVER Connect',
        'partner.fastcampus': 'FastCampus',
        'partner.modulabs': 'MODULABS',
        'partner.wanted': 'WantedLab',
        'partner.sparta': 'Sparta Coding Club',
        'partner.elice': 'Elice',
        'partner.day1': 'Day1Company',
        'partner.codeit': 'Codeit',

        // Ambassador
        'ambassador.codex': 'Codex Ambassador',

        // Footer
        'footer.rights': 'All rights reserved.'
    },
    ko: {
        // Navigation
        'nav.about': '소개',
        'nav.portfolio': '포트폴리오',
        'nav.more': '더 보기',
        'nav.experience': '경력',
        'nav.projects': '프로젝트',
        'nav.publications': '논문',
        'nav.teaching': '교육',
        'nav.ecosystem': 'Codex & DevX',
        'nav.ebook': 'E-book',
        'nav.media': '미디어',
        'nav.life': '일상',
        'nav.contact': '연락처',

        // Site
        'site.name': '한서우',
        'meta.title': '한서우 (Seowoo Han) | Applied AI Engineer · AX 교육자 · Codex Ambassador',
        'meta.description': 'Applied AI 엔지니어 한서우의 포트폴리오입니다. 컴퓨터 비전·OCR 제품, AX 교육, OpenAI Codex Ambassador 활동, 프로젝트·글·기사·발표 영상을 기록합니다.',

        // Hero
        'hero.name': '한서우입니다.',
        'hero.greeting': '안녕하세요, ',
        'hero.title': 'Applied AI Engineer · AX 교육자 · Developer Experience',
        'hero.education': '고려대학교 컴퓨터학과 박사 수료 · <a href="https://www.donga.com/news/Society/article/all/20190820/97026745/1" class="edu-link" target="_blank" rel="noopener">CMU AI 프로그램 (전액 장학, IITP 지원)</a>',
        'hero.description': 'Applied AI와 컴퓨터 비전을 실제 제품과 운영에 연결합니다. AX 교육과 OpenAI Codex Ambassador 활동을 통해 사람들이 AI를 자기 업무에서 검증하고 다시 사용할 수 있는 워크플로우를 만듭니다.',
        'hero.cta': '연락하기',
        'hero.projects': '프로젝트 보기',
        'hero.codexWork': 'Codex 작업 보기',
        'hero.codex101': 'Codex 101',
        'hero.portfolio': '대표 작업 보기',
        'hero.links': '대표 링크',

        // Portfolio overview
        'portfolio.kicker': 'Selected portfolio',
        'portfolio.title': '기술을 실제 제품, 업무, 학습 경험으로 연결합니다',
        'portfolio.intro': '엔지니어링, AX 교육, Codex 커뮤니티, 공개 콘텐츠를 따로 나열하지 않고 제가 맡은 역할과 확인 가능한 결과물로 연결했습니다.',
        'portfolio.engineering.eyebrow': 'Engineering',
        'portfolio.engineering.title': 'Applied AI를 제품과 운영에 붙이는 엔지니어링',
        'portfolio.engineering.desc': '드론 영상, OCR, 객체 탐지, 멀티모달 데이터가 실제 사용자 흐름에서 작동하도록 입력·예외·검증 단계를 설계합니다.',
        'portfolio.engineering.cta': '경력과 프로젝트 보기 →',
        'portfolio.codex.eyebrow': 'Codex & DevX',
        'portfolio.codex.title': 'Codex 101과 실전 개발자 워크플로우',
        'portfolio.codex.desc': '한국어와 영어 가이드, 데모, 온보딩 자료를 만들어 새로운 기능을 실제 개발 흐름에 연결합니다.',
        'portfolio.codex.cta': 'Codex 101 열기 ↗',
        'portfolio.ax.eyebrow': 'AX & Education',
        'portfolio.ax.title': '업무 하나를 직접 바꾸는 AX 교육',
        'portfolio.ax.desc': '기능 소개보다 문제 정의, 실행, 사람의 검토와 재시도를 중심으로 실습형 강의와 워크숍을 설계합니다.',
        'portfolio.ax.cta': 'AX Skillathon 기록 보기 ↗',
        'portfolio.community.eyebrow': 'Community',
        'portfolio.community.title': '다른 사람의 작업이 다음 실험이 되는 커뮤니티',
        'portfolio.community.desc': 'Workflow Show & Tell과 Codex 워크숍에서 사례를 모으고, 사람과 프로그램을 연결하며 결과를 공개 기록으로 남깁니다.',
        'portfolio.community.cta': '결과 페이지 보기 ↗',

        // About
        'about.title': '소개',
        'about.intro': '저는 <strong>AI Engineer & Developer Experience</strong>를 중심으로 일합니다. 실전 AI 시스템, 개발자 워크플로우, 학습 자료를 만들어 새로운 AI 역량이 실제 제품으로 이어지도록 돕습니다.',
        'about.education.korea': '🎓 고려대학교 컴퓨터학과 박사 수료 (ABD)',
        'about.education.cmu': '🇺🇸 Carnegie Mellon University AI 집중 프로그램 수료 (IITP 전액 국가 장학, 전국 31명 선발)',
        'about.education.combined': '🎓 고려대학교 컴퓨터학과 박사 수료 · <span class="edu-secondary">CMU AI 집중 프로그램 (IITP 국가 장학)</span>',
        'about.skills': '기술 스택',
        'about.education': '학력',
        'about.edu.korea': '컴퓨터공학 박사 수료 (ABD)',
        'about.edu.cmu': 'AI 집중 프로그램 (IITP 전액 장학, 전국 31명 선발)',
        'about.edu.khu.ms': '전자공학 석사',
        'about.edu.khu.bs': '전자공학 학사, 최우수 졸업',

        // Experience
        'experience.title': '경력',
        'exp.bgarage.narrative': '물류 재고 조사 자동화를 위해 드론을 활용하는 시스템을 개발했습니다. 창고 환경에서 드론이 찍은 이미지에서 라벨 정보를 추출하는 비전 AI 시스템을 개발했고, 드론 안전 자율주행을 위한 perception 시스템을 고도화하고 있습니다.',
        'exp.visit.narrative': '기존 360° 파노라마 카메라 앱 RoundPic의 고도화를 리드했습니다. 5명의 엔지니어 팀과 함께 AI 기반 Inpainting 및 Stitching 알고리즘을 개선해 파노라마 이미지의 눈에 띄는 이음새 문제를 해결했고, 2개월 만에 고객사를 3배로 성장시켰습니다.',
        'exp.viewmagine.narrative': 'AI 기반 인프라 검사를 위한 기술 전략을 총괄했습니다. VODA 시스템은 드론 영상으로 0.01mm 정밀도의 건물 균열을 탐지합니다.',
        'exp.keti.company': '한국전자기술연구원',
        'exp.keti.narrative': '스마트시티 인프라를 위한 실시간 교통 모니터링 AI를 개발했습니다. YOLO와 DeepSORT로 다중 CCTV 피드에서 98% 정확도를 달성했고, 이 연구로 2편의 국제 논문을 발표했습니다.',
        'exp.webarter.narrative': 'CMU에서 미국 대학생을 타겟으로 소셜 미디어 스타트업을 창업했습니다. 필터 버블을 깨고 다양한 관점을 보여주는 것이 미션이었습니다. Flutter와 ML 추천 시스템으로 앱을 만들었고, 사람들이 실제로 사용하는 제품을 출시하는 법을 배웠습니다.',
        'exp.cesInterview': 'CES 2023 AVING 인터뷰',
        'exp.linkedinPost': 'LinkedIn 글',
        'exp.githubRepo': 'GitHub 레포',
        'exp.aihubDataset': 'AIHub 데이터셋',

        'projects.title': 'AI-native 프로젝트',
        'projects.kicker': 'Project archive',
        'projects.portfolioIntro': '제품, 클라이언트 작업, 임팩트 프로젝트와 초기 실험을 확인된 범위와 공개 링크로 구분해 기록합니다.',
        'projects.order.beatpaws': '01 · Codex 데모 / 교육 자산',
        'projects.order.kibbl': '02 · AI 제품 아키텍처',
        'projects.order.zet': '03 · Agent/client 워크플로우',
        'projects.order.dva': '04 · 프로덕션 임팩트 작업',
        'projects.order.impactbridge': '05 · 임팩트 MVP',
        'projects.order.retext': '06 · 접근성 AI',
        'projects.order.explore': '07 · 초기 실험 아카이브',
        'projects.order.findleader': '08 · 시민 기술 실험 아카이브',
        'projects.order.webarter': '09 · 스타트업/제품 리더십',
        'projects.beatpaws.title': 'Codex로 만든 BeatPaws',
        'projects.beatpaws.desc': 'Vibe Jam 2026을 위해 Codex로 실제 플레이 가능한 웹 리듬 게임을 만들고, 그 제작 과정을 반복 루프, 플레이 테스트, 피드백, AI-written code의 제품화 관점에서 개발자 대상 발표로 정리했습니다.',
        'projects.impactbridge.title': '임팩트브릿지',
        'projects.impactbridge.desc': '사회혁신가와 기술 인재를 연결하는 플랫폼. 카카오임팩트 지원.',
        'projects.retext.desc': '시니어와 저시력자를 위한 AI 문서 요약. 접근성 중심 UX 설계.',
        'projects.findleader.title': '나의 리더를 찾아서',
        'projects.findleader.desc': '선거 기간에 후보 입장을 비교해볼 수 있도록 만든 시민 기술 실험 아카이브입니다. 캠페인 기간 동안 2,000+ 사용자가 이용했습니다.',
        'projects.explore.desc': '"나다움"을 표현하는 문장을 생성하던 초기 프로토타입 아카이브입니다. React와 AWS Lambda로 빠르게 만든 실험입니다.',
        'projects.kibbl.desc': '컴퓨터 비전, LLM, 벡터 검색, 구조화된 영양 데이터, RESTful API를 결합한 AI 기반 음식 분석 아키텍처를 설계했습니다.',
        'projects.zet.desc': '광고 전략, 장면 구조, 시각 레이아웃, 브랜드 맥락에 맞는 캠페인 콘셉트를 생성하는 AI agent 기반 크리에이티브 자동화 워크플로우를 구축했습니다.',
        'projects.techabreak.title': 'Tech a Break',
        'projects.techabreak.desc': '인터뷰 형식의 시즌 1을 마치고, 지금은 한서우의 생각을 기록하고 있습니다.',
        'projects.dva.desc': 'Tech for Impact 파일럿 기수로 약 2년간 진행한 비영리 협업 프로젝트. 제주 남방큰돌고래의 서식지 보존을 위해 관광 보트를 AI로 탐지·추적하는 웹 솔루션을 개발했습니다.',
        'projects.dva.kickoff': '킥오프 미팅',
        'projects.dva.journey': '프로젝트 로그',
        'projects.dva.partnership': '테크포임팩트 협약',
        'projects.dva.moducon': 'MODUCON 발표',
        'projects.dva.season2': '2기 시작',
        'projects.dva.usertest': '유저 테스트',
        'projects.dva.documentary': '미니다큐',
        'projects.dva.media': '미디어 & 아티클',
        'projects.dva.modulabs': '모두의연구소 블로그',
        'projects.dva.brunch': '카카오임팩트 브런치',
        'projects.badge.kakao': '카카오임팩트 지원',
        'projects.badge.personal': '개인 프로젝트',
        'projects.badge.team': '팀 프로젝트',
        'projects.badge.client': '클라이언트 작업',
        'projects.badge.codexDemo': 'Codex 데모',
        'projects.roundpic.desc': 'AI 기반 Inpainting 및 Stitching 알고리즘을 고도화한 360° 파노라마 이미지 생성 앱',
        'projects.voda.desc': '드론 기반 건물 결함 분석 및 균열 탐지 시스템',
        'projects.traffic.title': '교통 분석',
        'projects.traffic.desc': 'CCTV 조감도 변환을 활용한 실시간 교통 흐름 분석',
        'projects.posvision.desc': 'OCR 기반 주차장 관리 및 번호판 인식 시스템',
        'projects.webarter.desc': 'CTO/Co-founder. ML 추천 시스템을 적용한 미국 대학생 소셜 네트워크 서비스.',
        'projects.viewMore': '미니다큐',
        'projects.tryApp': '앱 체험',
        'projects.readNewsletter': '뉴스레터 읽기',
        'projects.devStory': '개발 스토리',
        'projects.experiment': '실험 회고',

        'publications.title': '논문',
        'publications.intlJournals': '국제 저널',
        'publications.intlConfs': '국제 학회',
        'publications.domestic': '국내 논문',
        'publications.viewPaper': '논문 보기',

        // Life
        'life.title': '일상 & 취미',
        'life.travel.title': '여행',
        'life.travel.desc': '스위스, 영국, 체코, 독일, 프랑스, 미국, 태국, 괌, 일본, 중국, 남아프리카공화국 등 여러 나라를 여행했습니다. 익숙한 환경에서 벗어나 새로운 문화와 생활 방식을 경험하는 것을 좋아합니다.',
        'life.camping.title': '캠핑',
        'life.camping.desc': '자연 속에서 화면과 잠시 거리를 두고, 천천히 쉬는 시간을 좋아합니다.',
        'life.nightsky.title': '밤하늘 구경',
        'life.nightsky.desc': '지구과학에 관심이 많습니다. 별과 달, 계절에 따라 달라지는 하늘을 바라보는 것을 좋아합니다.',
        'life.coding.title': '사이드 프로젝트',
        'life.coding.desc': '아이디어가 떠오르면 작은 형태로 먼저 만들고, 직접 사용하면서 발전시킵니다.',
        'life.photo.title': '사진',
        'life.photo.desc': '여행지와 일상의 장면을 사진으로 기록합니다. 좋아하는 순간을 오래 남기는 방법입니다.',
        'life.books.title': '독서',
        'life.books.desc': '기술부터 에세이까지 다양한 장르의 책을 읽으며 새로운 관점과 질문을 발견합니다.',

        // Teaching
        'teaching.title': '교육 활동',
        'teaching.intro': 'AI와 컴퓨터 비전 분야의 지식을 다양한 교육 플랫폼을 통해 전달하고 있습니다.',
        'teaching.cat.instructor': '강사',
        'teaching.cat.mentor': '튜터 & 멘토',
        'teaching.cat.ambassador': '앰배서더',
        'teaching.topic.cv': '컴퓨터 비전',
        'teaching.topic.chatgpt': 'ChatGPT & 생성형 AI',
        'teaching.topic.ethics': 'AI 윤리',
        'teaching.topic.career': 'AI 커리어',
        'teaching.topic.programming': 'AI 개론',
        'teaching.topic.career.mentor': '커리어',
        'teaching.topic.ai_mentoring': 'AI 멘토링',
        'teaching.topic.ocr': 'OCR 챌린지',
        'teaching.topic.ds': '데이터 사이언스 & AI',
        'teaching.topic.bootcamp': 'AI 부트캠프',
        'teaching.platform.fastcampus': '패스트캠퍼스',
        'teaching.platform.teamsparta': '팀스파르타 / 스파르타코딩클럽',
        'teaching.platform.modulabs': '모두의연구소',
        'teaching.platform.wantedlab': '원티드랩',
        'teaching.platform.elice': '엘리스 코딩',
        'teaching.platform.codeit': '코드잇',
        'teaching.platform.cv_mentor': '멋쟁이사자처럼, 업스테이지, 데이원컴퍼니',
        'teaching.platform.ocr_mentor': '업스테이지, 데이원컴퍼니',
        'teaching.platform.naver': '네이버 커넥트재단',
        'teaching.platform.sparta': '스파르타코딩클럽, 코드잇',

        // Talks
        'nav.talks': '발표',
        'talks.title': '초청 발표',
        'talks.type.panel': '패널 토크',
        'talks.beatpaws.title': 'Codex로 만든 BeatPaws 제작기',
        'talks.beatpaws.subtitle': '단국대 Tech for !mpact for Campus',
        'talks.beatpaws.desc': '단국대 Tech for !mpact for Campus 수업에서 Vibe Jam 2026 참여작 BeatPaws를 Codex로 만든 과정을 나눈 1시간 세션. AI-written code가 실제로 플레이할 만한 게임이 되려면 작은 플레이 루프, 직접 플레이 검증, 피드백, 반복 개선이 필요하다는 점을 중심으로 이야기했습니다.',
        'talks.beatpaws.youtube': '한글 강의 발표 영상',
        'talks.iwd.title': "International Women's Day: Female Leadership in AI",
        'talks.iwd.subtitle': '주한 캐나다대사관 · 주한영국대사관 공동 주최',
        'talks.iwd.desc': '2026년 3월 9일에 열리는 행사에 패널 토크 연사로 초청되었습니다. AI 분야에 관심 있는 학부/대학원생 및 커리어 초기 실무자 등 35명이 등록한 자리입니다.',
        'talks.leadher.subtitle': 'AI 시대, 직함이 아니라 브랜드가 나를 살린다',
        'talks.leadher.desc': '80여 명의 여성 개발자들과 함께한 자리. AI가 가져올 미래는 예측 불가능하지만, 지나친 회의주의나 맹목적 낙관주의를 경계하며 균형 잡힌 시각으로 변화에 능동적으로 대응해야 합니다.',
        'talks.aiconf.title': '돕는AI컨퍼런스 2025',
        'talks.aiconf.subtitle': '카카오임팩트 x 사회가치페스타',
        'talks.aiconf.desc': '카카오임팩트 x 사회가치페스타에서 AI for Good과 Tech for Impact에 대한 발표.',
        'talks.code.subtitle': '개발자 리더십의 비밀',
        'talks.code.desc': '리더십에서 "나"와 "우리"의 균형에 대한 세션. 리더십에 정해진 공식은 없으며, 모두가 다르게 리드하고, 팔로워십도 그만큼 중요합니다.',
        'talks.modupop.subtitle': 'DVA LAB: 해양 생태계 AI 모니터링',
        'talks.modupop.desc': '제주 돌고래 보호를 위한 Vision AI 기반 드론 영상 분석 웹서비스 - BEV 변환을 활용한 선박 속도 추정.',
        'talks.jeju.desc': 'AI 기반 선박 탐지 및 추적 기술을 활용한 제주 남방큰돌고래 보호에 관한 발표.',
        'talks.digilab.subtitle': '기술로 세상을 바꾸다',
        'talks.digilab.desc': '실시간 드론 비전 시스템에서 영감을 받은 남방큰돌고래 AI 보전 활동에 대한 발표.',
        'talks.wtm.desc': 'DVA LAB의 사회적 임팩트 프로젝트에서 얻은 교훈을 바탕으로 신기술이 미래를 어떻게 형성할 수 있는지에 대한 발표.',
        'talks.moducon.desc': 'DVA LAB에서 영감을 받아 협업 AI 프로젝트를 통해 개인의 재능을 모아 사회 문제를 해결한 여정에 대한 발표.',
        'talks.google.desc': '필터 버블을 깨고 다양한 관점을 볼 수 있도록 하는 데 초점을 맞춘 미국 대학생 대상 소셜 미디어 스타트업을 창업했습니다.',
        'talks.posco.title': '포스코E&C 스마트 건설 아카데미',
        'talks.posco.desc': 'AI 활용 및 건설 기술의 긍정적 영향력에 대한 초청 강연.',
        'talks.watchVideo': '영상 보기',
        'talks.talkReview': '발표 후기',
        'talks.watchReplay': '발표 다시보기',
        'talks.eventInfo': '행사 소개',

        // Experience
        'exp.interview': '인터뷰',
        'exp.viewmagine.narrative': 'AI 기반 인프라 검사를 위한 기술 전략을 총괄했습니다. VODA 시스템은 드론 영상으로 0.01mm 정밀도의 건물 균열을 탐지합니다. CES 2023에서 회사를 대표하여 드론 기반 균열 탐지 기술을 선보였습니다.',

        // Contact
        'contact.title': '연락하기',
        'contact.text': '새로운 프로젝트, 창의적인 아이디어, 또는 함께할 기회에 대해 언제든 연락해 주세요.',

        // Media
        'media.title': '미디어 & 아카이브',

        // Codex & Developer Experience
        'ecosystem.title': 'Codex & 개발자 경험',
        'ecosystem.ambassador.desc': '실전 가이드, 데모, 워크숍, 피드백 루프를 통해 한국 개발자들이 Codex를 제품 개발에 연결하도록 돕습니다.',
        'ecosystem.proof.guide.label': '가이드',
        'ecosystem.proof.guide': 'OpenAI Developers Showcase에 소개된 한/영 실전 가이드 Codex 101을 만들고 유지하고 있습니다.',
        'ecosystem.proof.community.label': '커뮤니티',
        'ecosystem.proof.community': 'OpenAI Korea와 IT\'s Study 커뮤니티를 연결해 실전 학습 프로그램을 기획하고, 한국 개발자와 빌더를 대상으로 Codex 밋업, 데모, 워크숍, 온보딩 세션을 진행했습니다.',
        'ecosystem.proof.feedback.label': '피드백',
        'ecosystem.proof.feedback': '설문 115개 응답과 57개 주관식 코멘트에서 한국 Codex 사용자 피드백을 구조화해 DevX 인사이트로 정리했습니다.',
        'ecosystem.latest.label': '최근 공개 작업',
        'ecosystem.latest.date': '2026년 7월',
        'ecosystem.latest.roboflow.kicker': 'Roboflow MCP',
        'ecosystem.latest.roboflow.title': 'Codex + Roboflow MCP로 냉장고 유통기한 웹앱 만들기',
        'ecosystem.latest.roboflow.desc': 'MCP 도구 탐색, 공개 데이터셋 read-only 검색, 안전한 키 분리, 컴퓨터 비전 inference를 앱 흐름으로 연결하는 실전 기록입니다.',
        'ecosystem.latest.onboarding.kicker': 'Codex 온보딩',
        'ecosystem.latest.onboarding.title': "ChatGPT App으로 내 업무 맡기기 - 제5차 개정판",
        'ecosystem.latest.onboarding.desc': "ChatGPT 앱으로 실제 업무를 맡기는 무료 가이드입니다. 비개발자는 Chat·Work, 개발자는 Codex에서 시작해 보세요. 두 공간의 업무 범위는 겹치므로 익숙한 화면을 선택하면 됩니다. 2026.09.05 제5차 개정판은 GPT-6 Astra와 모델 선택, 새 화면 21장, 업무를 이어가고 결과를 검토하는 방법을 담았습니다.",
        'ecosystem.latest.workflowShowTell.kicker': 'Workflow Show & Tell Seoul',
        'ecosystem.latest.workflowShowTell.title': '2026 결과 페이지',
        'ecosystem.latest.workflowShowTell.desc': '행사 결과와 참가자 워크플로우, 실전 AI 업무를 둘러싼 커뮤니티 경험을 공개 기록으로 정리한 페이지입니다.',
        'ecosystem.techabreak.date': '시즌 1 종료',
        'ecosystem.techabreak.desc': '인터뷰 형식의 시즌 1을 마치고, 지금은 한서우의 생각을 기록하고 있습니다.',
        'ecosystem.btn.linkedin': '📝 링크드인',
        'ecosystem.btn.youtube': '▶️ 유튜브',
        'ecosystem.btn.articles': '📰 아티클',
        'ecosystem.btn.lectures': '🎤 강의·강연',
        'ecosystem.btn.events': '🎪 행사',
        'ecosystem.btn.mediaCoverage': '🗞️ 언론 보도',
        'ecosystem.btn.series': '✉️ 시리즈',
        'ecosystem.comingSoon': '업데이트 예정',
        'ecosystem.article.codex101': 'Codex 101 - OpenAI Codex 완전 가이드',
        'ecosystem.article.aiAgent': 'AI Agent 개념 이해하기',
        'ecosystem.article.codexBestPractices': 'OpenAI Codex Best Practices 한국어 정리',
        'ecosystem.article.roboflowMcp': 'Codex + Roboflow MCP 냉장고 유통기한 웹앱',
        'ecosystem.article.agentWorkflow': '에이전트 시대, 우리가 설계해야 할 것은 모델이 아니라 시스템이다',
        'ecosystem.article.dearHumans': 'Dear, Humans: 딸깍의 시대에 우리는 왜 여전히 자기 삶을 살아봐야 할까',
        'ecosystem.article.codexSimple': 'Codex, 쉽게 말해본다면',
        'ecosystem.article.plugins': 'Codex에서 Plugin이 실제로 어떻게 동작하는가',
        'ecosystem.link.codexAnnouncement': 'OpenAI Codex Ambassador 선정 소식',
        'ecosystem.link.meetupRecruitment': 'Codex Community Meetup - Seoul 3.11 개최 후기',
        'ecosystem.link.codex101Story': 'Codex 101을 만들게 된 이야기',
        'ecosystem.link.aiAgentStory': 'AI Agent 개념 이해하기를 쓰게 된 이야기',
        'ecosystem.link.ralphtonRecap': '2026.02.28-03.01 Ralphton 참관 후기',
        'ecosystem.link.codexForOpenSource': 'Codex for Open Source 프로그램 소개',
        'ecosystem.link.codexWebinar': 'OpenAI 웨비나: Codex 멀티 에이전트 워크플로우',
        'ecosystem.link.codexImpactRecap': '2026.06.27 Codex Impact Workshop 결과 공유',
        'ecosystem.link.workflowShowTellRecap': 'Workflow Show & Tell Seoul 2026 행사 후기',
        'ecosystem.link.itsStudyPlanning': "IT's Study: OpenAI Korea 협업 연결 및 프로그램 기획",
        'ecosystem.link.day1AxSkillathon': 'Day1 Company AX Skillathon: Codex와 Skill 제작 강의',
        'ecosystem.lecture.day1AxSkillathon': '2026.07.13 Day1 Company AX Skillathon - Codex 활용과 Skill 제작 실습',
        'ecosystem.lecture.companyAxOnboarding': '2026.07.25 안전진단 S사 기업 AX 온보딩 - Codex 실무 교육',
        'ecosystem.lecture.parentsDayAi': '2026.05.08 OpenAI x 패스트캠퍼스 AI 어버이날 - Codex 메인 강의',
        'ecosystem.link.roboflowMcpPost': '2026.06.08 Codex + Roboflow MCP 아티클',
        'ecosystem.link.codexOnboardingPdf': '2026.06 Codex 온보딩 PDF 공유 글',
        'ecosystem.link.techabreak.substack': 'Tech a Break 읽기',
        'ecosystem.link.techabreak.story': 'Tech a Break를 시작한 이유',
        'ecosystem.youtube.plainBusinessmanEp1': '평범한 사업가 1화 - Codex 앱 기본 사용과 작업 흐름',
        'ecosystem.youtube.plainBusinessmanEp2': '평범한 사업가 2화 - Sites·Ultra·Side Chat 실전 워크플로우',
        'ecosystem.link.parentsDayOfficialVideo': 'Official OpenAI 영상: AI 어버이날 행사',
        'ecosystem.event.meetupHost': '2026.03.11 Codex Community Meetup - Seoul (단독 호스트)',
        'ecosystem.event.codexImpactWorkshop': '2026.06.27 Codex Impact Workshop',
        'ecosystem.event.workflowShowTellRecap': '2026.07.13 Workflow Show & Tell Seoul',
        'ecosystem.event.workflowShowTell': '2026 Workflow Show & Tell Seoul 결과 페이지',
        'ecosystem.event.ralphtonSponsor': '2026.02.28-03.01 Ralphton (커뮤니티 후원)',
        'ecosystem.media.codexImpactVentureSquare': '벤처스퀘어: AI가 사회혁신가의 동료가 된 하루',
        'ecosystem.media.codexImpactTheButter': '더버터: 사회문제 해결 돕는 AI 솔루션',
        'ecosystem.media.parentsDayYtnYoutube': '"카네이션 대신 AI" YTN 영상',
        'ecosystem.media.parentsDayNaverTv': '"자식과 함께 AI로 앱 만들어요" 네이버TV',
        'ecosystem.media.parentsDayYtnArticle': '[자막뉴스] 시니어들 사이 퍼진 AI 열풍',

        // E-book
        'ebook.label': '무료 PDF',
        'ebook.price': '0원 무료',
        'ebook.title': "ChatGPT App으로 내 업무 맡기기 - 제5차 개정판",
        'ebook.desc': "ChatGPT 앱으로 실제 업무를 맡기는 무료 가이드입니다. 비개발자는 Chat·Work, 개발자는 Codex에서 시작해 보세요. 두 공간의 업무 범위는 겹치므로 익숙한 화면을 선택하면 됩니다. 2026.09.05 제5차 개정판은 GPT-6 Astra와 모델 선택, 새 화면 21장, 업무를 이어가고 결과를 검토하는 방법을 담았습니다.",
        'ebook.readingNote': 'AI에게 이 책을 요약하게 하지 마세요. 직접 1-2시간 시간을 내서 읽으세요. 그만한 가치가 있습니다.',
        'ebook.previewTitle': '담긴 내용 · 목차',
        'ebook.preview.item1': "Chat·Work·Codex에서 업무에 맞게 시작하기",
        'ebook.preview.item2': 'Work 로컬·클라우드 차이와 다중 source folder 연결하기',
        'ebook.preview.item3': "Voice·Pet, Chrome 확장과 Sites 활용 안내",
        'ebook.preview.item4': 'AGENTS.md와 메모리로 작업 원칙 남기기',
        'ebook.preview.item5': "Goal·예약의 환경별 차이와 긴 작업 운영하기",
        'ebook.preview.item6': 'Skill을 만들고 반복 업무 시스템화하기',
        'ebook.preview.item7': "Astra Medium부터 조정하기 · 사용량과 리셋권 확인",
        'ebook.preview.item8': "업무 결과 화면 · 여러 Gmail 계정 · 문서 검증 체크리스트",
        'ebook.meta.versionLabel': '버전',
        'ebook.meta.version': "제5차 개정판 · 2026.09.05",
        'ebook.meta.formatLabel': '형식',
        'ebook.meta.format': "PDF · 96쪽",
        'ebook.meta.updateLabel': '업데이트',
        'ebook.meta.update': "2026.09.05 콘텐츠 개정",
        'ebook.downloadCountLabel': '다운로드',
        'ebook.downloadCountUnavailable': '집계 준비 중',
        'ebook.download': 'PDF 다운로드',
        'ebook.getFreeOnLatpeed': '판매 페이지 보기',
        'ebook.all': '전체 e-book 보기',
        'ebook.note': '무료 PDF는 바로 내려받을 수 있고, 유료 전자책은 판매 페이지에서 구성과 구매 안내를 확인할 수 있습니다.',
        'ebook.home.title': 'E-books',
        'ebook.home.desc': 'AI 시대의 일과 커리어를 돌아보는 에세이부터 Codex 실전 가이드와 IT 용어집까지, 직접 만든 전자책을 모았습니다.',
        'ebook.home.codex.point1': "Chat·Work·Codex에서 내 업무에 맞는 시작점 찾기",
        'ebook.home.codex.point2': "Astra Medium부터 시작하고 Voice·Chrome·Sites 살펴보기",
        'ebook.home.codex.point3': "이전 대화·Gmail 계정 연결과 문서 검증·반복 업무 익히기",
        'ebook.related.pangyo.title': '판교어 사전',
        'ebook.related.pangyo.desc': 'AI 바이브코딩 협업 전에 보는 IT · 개발 · 스타트업 용어 240',
        'ebooks.label': '자료실',
        'ebooks.title': 'E-books',
        'ebooks.desc': 'AI 시대의 일과 커리어를 돌아보는 에세이부터 Codex 실전 가이드와 IT 용어집까지, 직접 만든 전자책을 모았습니다.',
        'ebooks.portfolioCta': '포트폴리오 섹션',
        'ebooks.detailCta': '상세 보기',
        'arrow.label': '유료 전자책',
        'arrow.price': '16,900원',
        'arrow.title': '열심히 살수록 내가 사라졌다',
        'arrow.desc': 'AI 시대의 일과 커리어를 돌아보며, 남의 기대와 직함 밖에서 내 기준을 세우는 과정을 담은 에세이입니다. 자신의 경험을 다시 해석할 질문과 워크북도 함께 제공합니다.',
        'arrow.readingNote': '본문 83쪽과 ‘나의 화살 지도’ 워크북 17쪽이 하나의 100쪽 PDF에 포함됩니다.',
        'arrow.previewTitle': '이 책이 건네는 질문',
        'arrow.preview.item1': '반복해서 해결한 문제로 강점 찾기',
        'arrow.preview.item2': '성장 욕구와 자기 증명 욕구 구분하기',
        'arrow.preview.item3': '역할·보상·종료 조건으로 경계 세우기',
        'arrow.preview.item4': '피드백을 가치와 의도로 걸러내기',
        'arrow.preview.item5': '다음 30일의 가장 작은 실험 정하기',
        'arrow.meta.version': '초판 · 2026.07',
        'arrow.meta.format': 'PDF · 100쪽',
        'arrow.meta.includedLabel': '포함',
        'arrow.meta.included': '워크북 17쪽',
        'arrow.cta': '판매 페이지 보기',
        'arrow.deadline': '많은 분들이 관심 가져주셔서 2026년 9월 30일까지 판매를 연장합니다.',
        'arrow.closed': '판매 종료',
        'arrow.closedNote': '한정 판매 기간이 종료되었습니다.',
        'arrow.externalNote': '클릭하면 래피드 판매 페이지가 새 탭에서 열립니다.',
        'pangyo.label': '무료 PDF',
        'pangyo.price': '0원 무료',
        'pangyo.title': '판교어 사전',
        'pangyo.desc': 'AI로 직접 만들기 시작한 비개발자와 사무직을 위한 IT 실전 용어집입니다. 스펙, API, 배포, QA, MVP처럼 만들다 보면 계속 마주치는 말을 가볍게 익히고, 개발자와 더 편하게 이야기할 수 있도록 정리했습니다.',
        'pangyo.readingNote': '"어제 얼라인한 스펙, 아삽으로 컨펌 부탁드려요" 같은 문장이 조금 덜 낯설어지게 만드는 협업용 용어집입니다.',
        'pangyo.previewTitle': '담긴 내용 · 목차',
        'pangyo.preview.item1': '회의·소통: 얼라인, 싱크, 컨펌, 팔로업, 스크럼',
        'pangyo.preview.item2': '업무 진행: 리소스, 듀데잇, 스코프, 블로커, 오너십',
        'pangyo.preview.item3': '개발 실전: 배포, 롤백, QA, 코드리뷰, API, 바이브코딩',
        'pangyo.preview.item4': '기획·데이터: MVP, PoC, 애자일, 퍼널, 리텐션, SQL',
        'pangyo.preview.item5': 'AI·스타트업 씬: LLM, RAG, 피칭, 밸류에이션, PMF',
        'pangyo.meta.version': '2026.07.02',
        'pangyo.meta.format': 'PDF · 18 pages',
        'pangyo.meta.update': 'Drive 파일 버전 관리',

        'media.profile.title': '원티드랩 인물도감',
        'media.profile.desc': '일의 의미, 직장 내 스트레스와 가스라이팅을 극복한 경험, 그리고 그 과정에서 배운 것들에 대한 솔직한 이야기.',
        'media.btn.article': '인물도감 보러가기',
        'media.btn.youtube': '유튜브 보러가기',
        'media.modulabs.title': 'DVA LAB 스토리',
        'media.modulabs.desc': '기술 실험을 위한 "안전한 온실"을 만들고 커뮤니티 주도 AI 프로젝트를 이끄는 이야기.',
        'media.plainBusinessmanEp1.title': '평범한 사업가 AI 팟캐스트 #87',
        'media.plainBusinessmanEp1.desc': 'Codex 앱의 기본 사용과 작업 흐름을 설명한 인터뷰.',
        'media.plainBusinessmanEp2.title': '평범한 사업가 AI 팟캐스트 #92',
        'media.plainBusinessmanEp2.desc': 'Sites·Ultra·Side Chat을 실제 업무 흐름으로 연결한 인터뷰.',

        // Partners
        'partner.likelion': '멋쟁이사자처럼',
        'partner.naver': '네이버 커넥트재단',
        'partner.fastcampus': '패스트캠퍼스',
        'partner.modulabs': '모두의연구소',
        'partner.wanted': '원티드랩',
        'partner.sparta': '스파르타코딩클럽',
        'partner.elice': '엘리스',
        'partner.day1': '데이원컴퍼니',
        'partner.codeit': '코드잇',

        // Ambassador
        'ambassador.codex': 'Codex Ambassador',

        // Footer
        'footer.rights': 'All rights reserved.'
    }
};

// Current language
let currentLang = 'en';

// Detect browser language
function detectLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    // Check if Korean
    if (browserLang.startsWith('ko')) {
        return 'ko';
    }
    return 'en';
}

// Apply translations
function applyTranslations(lang) {
    if (!translations[lang]) {
        lang = detectLanguage();
        if (!translations[lang]) {
            lang = 'en';
        }
    }

    currentLang = lang;
    const elements = document.querySelectorAll('[data-i18n]');

    elements.forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[lang] && translations[lang][key]) {
            // Use innerHTML if translation contains HTML tags
            const translation = translations[lang][key];
            if (translation.includes('<') && translation.includes('>')) {
                el.innerHTML = translation;
            } else {
                el.textContent = translation;
            }
        }
    });

    // Handle data-i18n-html for HTML content translations
    const htmlElements = document.querySelectorAll('[data-i18n-html]');
    htmlElements.forEach(el => {
        const key = el.getAttribute('data-i18n-html');
        if (translations[lang] && translations[lang][key]) {
            el.innerHTML = translations[lang][key];
        }
    });

    // Show language-specific elements only in their matching locale.
    document.querySelectorAll('[data-lang-only]').forEach(el => {
        const shouldShow = el.getAttribute('data-lang-only') === lang;
        el.hidden = !shouldShow;
        el.style.display = shouldShow ? '' : 'none';
    });

    // Point bilingual external references to the matching source language.
    document.querySelectorAll('[data-href-en][data-href-ko]').forEach(el => {
        el.setAttribute('href', el.getAttribute(`data-href-${lang}`));
    });

    document.querySelectorAll('[data-alt-en][data-alt-ko]').forEach(el => {
        el.setAttribute('alt', el.getAttribute(`data-alt-${lang}`));
    });

    document.querySelectorAll('[data-aria-en][data-aria-ko]').forEach(el => {
        el.setAttribute('aria-label', el.getAttribute(`data-aria-${lang}`));
    });

    // Update HTML lang attribute
    document.documentElement.lang = lang;

    // Keep the browser title and share metadata aligned with the selected language.
    // Subpages can provide page-specific metadata on <body> instead of inheriting the home-page profile metadata.
    const metaSuffix = lang === 'ko' ? 'Ko' : 'En';
    document.title = document.body.dataset[`metaTitle${metaSuffix}`] || translations[lang]['meta.title'];
    const description = document.body.dataset[`metaDescription${metaSuffix}`] || translations[lang]['meta.description'];
    document.querySelector('meta[name="title"]')?.setAttribute('content', document.title);
    document.querySelector('meta[name="description"]')?.setAttribute('content', description);
    document.querySelector('meta[property="og:title"]')?.setAttribute('content', document.title);
    document.querySelector('meta[property="og:description"]')?.setAttribute('content', description);
    document.querySelector('meta[property="twitter:title"]')?.setAttribute('content', document.title);
    document.querySelector('meta[property="twitter:description"]')?.setAttribute('content', description);

    // Update language toggle button
    const langText = document.querySelector('.lang-text');
    if (langText) {
        langText.textContent = lang === 'ko' ? 'EN' : '한';
    }

    // Save preference
    localStorage.setItem('lang', lang);
}

// Toggle language
function toggleLanguage() {
    const newLang = currentLang === 'en' ? 'ko' : 'en';
    applyTranslations(newLang);
}

// Initialize i18n
function initI18n() {
    // Check localStorage first, then detect browser language
    const savedLang = (localStorage.getItem('lang') || '').toLowerCase();
    let lang = detectLanguage();
    if (savedLang.startsWith('ko')) {
        lang = 'ko';
    } else if (savedLang.startsWith('en')) {
        lang = 'en';
    }

    applyTranslations(lang);
}

// Export for main.js
window.i18n = {
    init: initI18n,
    toggle: toggleLanguage,
    apply: applyTranslations
};

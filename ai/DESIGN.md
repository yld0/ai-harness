# ai-harness

A financial AI harness to power an AI stock research platform (chat)

####

I want to build an AI harness, as a redesign/reimplementaton of the ai repo

There multiple references repos for ideas:
 - openclaude-main ~ A open source port of claude code
 - openclaw ~ A personal AI assistant you run on your own devices
 - claw-code ~ Is the public Rust implementation of the claw CLI agent harness
 - ai ~ my current implementation for the ai harness
 - hermes-agent-main ~ a python agent framework for self learning agents (This is written in python so a good example)


Analysis of repos:
- @openclaude-analysis.md
- @openclaw-analysis.md
- @claw-code-analysis.md

Generally some useful analysis in docs/


Other useful references:
- https://medium.com/ai-software-engineer/anthropics-new-harness-engineering-playbook-shows-why-your-ai-agents-keep-failing-174a5575ff92
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- https://medium.com/gitconnected/building-claude-code-with-harness-engineering-d2e8c0da85f0
- https://github.com/razakiau/claude-code
- https://ai.plainenglish.io/harness-engineering-understand-this-will-make-your-ai-agent-performs-better-than-80-other-agents-271c3efeec4c
- https://www.youtube.com/watch?v=RFKCzGlAU6Q
- https://github.com/nousresearch/hermes-agent
- https://medium.com/@lakkannawalikar/cursor-ai-architecture-system-prompts-and-tools-deep-dive-77f44cb1c6b0
- https://medium.com/data-science-collective/how-cursor-actually-works-under-the-hood-09eba11f8d21


Other repo references:
 - https://github.com/virattt/dexter

## Aim 

You are essentially revamping ./references/ai-master which is a websocket ai chat interface


- Websocket based ai chat
- Self learning agent behaviour
- We also like to be able to run the agent standalone (so some ability to do that without running the fastapi would be good)
  

## Requirements

- Four modes: auto, plan, explain, criticise (might need a field in pydantic schema)
    (different system prompts)
- Predefined agentic workflows (triggered by setting route field):
  - actions-catchup
  - actions-market-catchup
  - action-tldr-news
  - actions-recent-earnings
  - llm-council (replace llm_council)
  - spaces-* (can be a TDO)
- Slash commands (might need a new field in the schema)

- post hooks:
  - auto dream: Auto dream to streamline memories for a user
  - compact: Compact the conversation history
  - autonomous skill generation: Auto trigger async skill reviewer agent every 10 tool call steps 

- gateway to talk to it via whatsapp https://github.com/virattt/dexter/tree/main/src/gateway
- Use openrouter for non gemini models, for gemini use the main genai library (like in ai repo) directly. We want to use gemini flash unless require more thinking/reasoning or specified to use a specific model


### Spaces

- spaces-compact
  This is a special route that will compact the chat/s (can copy the existing )


### Tools

heartbeats/monitors - https://github.com/virattt/dexter/blob/main/src/tools/heartbeat/heartbeat-tool.ts


- search knowledge 

- a search tool  similar to https://github.com/virattt/dexter/blob/e471ef1e54965a14b1aabed33d3da3fb585ff07b/src/tools/search/index.ts maybe (but python)
export { tavilySearch } from './tavily.js';
export { exaSearch } from './exa.js';
export { perplexitySearch } from './perplexity.js';
export { xSearchTool, X_SEARCH_DESCRIPTION } from './x-search.js';




file operations:

grep - can search knowldege markdown files etc 

System

AskUserQuestion
- grep: grep tool, useful for search memories, files and otherwises from personal knowledge


internal:
 - fmp data
    maybe mcp, skill or search of tools ?
 - yld data
 - graphql based:
    - live real price?
    - metric based data 
    - previous thesis 
 - user-cli: add alerts, watchlists & update/delete
 - search_expert: Search financial expert knowledge from books (uses page index) (should NOT be implemented but scaffold out the tool)




### Plan Mode

Like plan mode in cursor, claude code the agent creates a temporary plan as a .md that the user can modify/question before trying to implement the plan.

Should use a specific plan mode prompt.


This will be useful for deep reports, analysis or complex questions and ensures the answer format is what the user wants 

ChatComponent = Union[ChatTableComponent, ChatChartComponent] ~ add another FileComponent or equivalent so user can view the plan 

Should be able to edit the plan you might need to be able to add 


### Criticise Mode

Should should the use a specific criticise prompt for a user opinion or thesis


### Spaces

 - Grounding 
 - Knowledge Base
 - Sources Knowledge

read @supergraph.graphql (spaces_*)
e.g. https://yld0.com/spaces/f601f866-1f53-4de4-93b6-89f6604253ac

### Thinking 

When waiting for an response, we should output a verbal spinner like claude code. You can use the CotStep like in ai-main.


## Graphql api

There is a graphql api to add interactions etc. (see ai-main)


## Memory 


- para memory files using para-memory-files skill (paperclip)
- memories graphql (for user's memories and company relationships) (uses neo4j)
- need a way to know memory and ability to change it 

@DESIGN_MEMORIES.md



## Cron 

We can run automations by talking to the automations graphql endpoint automations_*

Automations subgraph will then call this ai harness

so we need a http endpoint to start shortlived agent 



## Design Guidance

- Routing can be explicit with 'route' field


### Generally
- User input a query with context 
- Wraps the text into the llm provider's message format
- Message gets pushed onto the in-memory conversation array
- Assemble system prompt from CLAUDE.md, tool defs, context, and memory
- In a loop, call LLM, check the output and valid if the response is good enough if not append to history and call llm again until (max loops hough) (think n0 loop that claude code uses generally)
- Render response
- Run post hooks: Auto-compact if conversation is too long


### skills

- add-skill
- patch-skill

- plan:  research cursor and  https://github.com/NousResearch/hermes-agent/blob/main/skills/software-development/plan/SKILL.md | https://github.com/NousResearch/hermes-agent/blob/main/skills/software-development/writing-plans/SKILL.md 
- para-memory-files: should be based of https://github.com/paperclipai/paperclip/tree/master/skills/para-memory-files
  

- arxiv https://github.com/NousResearch/hermes-agent/tree/main/skills/research
- blogwatcher https://github.com/NousResearch/hermes-agent/blob/main/skills/research/blogwatcher/SKILL.md - global or user??

https://github.com/NousResearch/hermes-agent/tree/main/skills/research/llm-wiki

https://github.com/NousResearch/hermes-agent/tree/main/skills/research/polymarket

https://github.com/NousResearch/hermes-agent/blob/main/skills/research/research-paper-writing/SKILL.md - change to report or aluation thesis


https://github.com/NousResearch/hermes-agent/tree/main/skills/note-taking


https://github.com/NousResearch/hermes-agent/blob/main/skills/media/youtube-content/SKILL.md

https://github.com/NousResearch/hermes-agent/blob/main/skills/social-media/xitter/SKILL.md



### Skill safe guarding 

We need to ensure skills added, used 

- have a look at skills_guard.py 


worth checking the other respositories for any other safe guarding concepts, code or techniques


### Autonomous skill generation 

User message → API call → Parse response → Execute tools → Feed results back → Repeat



## What I think from most of the repos 


- @hermes-agent-main ~ I like the skill reviewer & self evolving skill prompt & memory tiers
- @openclaw ~ allow easy adding of multiple skills and the use of multiple llm support. Ability to add gateway and notification channels
- https://github.com/virattt/dexter ~ is clear, simple and well structured





## Project structure guidance

I like simple and well structured folders to make it easier to debug and enhance with new features.
Some obvious suggestions (only suggestion can change if makes sense)
Below is non exhaustive

```
src/
    const.py    # constants variables
    deprecated/ # deprecated v2 implementation 
    api/ # graphql backend ai clients
    agent/
    providers/ # llm providers (might make sense )
    council/ # llm council 
    commands/ # slash commands 
              base.py # base slash command class
    gateway/ # gateway for whatsapp (should use neonize library) etc

    tools/ # tools
         <TOOL>/
    schemas/ # pydantic schemas for websocket, internals
    skills/ # skills
    hooks/  # post hooks (compact etc)
    telemetry/ # sentry, posthog etc (ai-master's telemetry files & folder)
              posthog.py
              sentry.py
    tasks/ # ai-master 's tasks folder & files
    usage/ # capture usage (see ai-master repo for more details)
        capture.py # ai-master's capture.py
    
    utils/ # miscellaneous utility functions
        caching/
          semantic.py # same as ai-master's semantic.py
        web/  # formerly web_utils in ai-master repo
           __init__.py
           description.py
           redirect.py
```




## Other notes


### Context management

- should run compaction if the conversation is too long
- context collapse (should collapse the context to stay within the model limits )

### System prompt generation

- Construction of the system prompt should be like dexter, constructing the system prompt taking into acccount the soul, channel etc. 
   https://github.com/virattt/dexter/blob/745687e3d68b08e8b23b1d0f34db424f3da8e3cd/src/agent/prompts.ts#L215
- Once per session we add the memory from disk, mid-session we dont insert into the system prompt. We do however update them memory on disk (see hermes agent and hermes-session-memory.md for general idea)

system prompt layer order (exluding rules)
1. SOUL.md (or DEFAULT_AGENT_IDENTITY)
2. Tool guidance (MEMORY_GUIDANCE, SKILLS_GUIDANCE, etc.)
3. User/gateway system message
4. ← MEMORY.md block here
5. ← USER.md block here
6. External memory provider block (if configured)
7. Skills prompt
8. Context files (AGENTS.md, .cursorrules, etc.)
9. Current date/time
10. Platform formatting hint

see also @hermes-personality-system.md

- Personality should use the SOUL.md but like hermes agent allow personality at the end of the system prompt (Injected at the **end** of the prompt stack, so it can supplement or override the baseline soul.)
   Come up with some personality 

   and add a command to switch the personality: /personality codereviewer
   

- Should also proocess AGENTS.md like hermes agent
- Should then grab the user rules (cached) from graphql backend and add them rules_alwaysApplyRules & rules_rules  (see @supergraph.graphql)


- Skills can be added similiar to openclaw

e.g. 
1. should be formatted into the system prompt

in claw code repo reference see src/agents/skills/skill-contract.ts:

eg in typescript
```
export function formatSkillsForPrompt(skills: Skill[]): string {
  const lines = [
    "\n\nThe following skills provide specialized instructions for specific tasks.",
    "Use the read tool to load a skill's file when the task matches its description.",
    // ...
    "<available_skills>",
  ];
  for (const skill of skills) {
    lines.push("  <skill>");
    lines.push(`    <name>${skill.name}</name>`);
    lines.push(`    <description>${skill.description}</description>`);
    lines.push(`    <location>${skill.filePath}</location>`);
    lines.push("  </skill>");
  }
  return lines.join("\n");
}
```

2. Skills section is built into the system prompt

https://github.com/openclaw/openclaw/blob/ac00ba1943d28c33ffd128131bee69402449685e/src/agents/system-prompt.ts#L151-L167

example in typescript
```
function buildSkillsSection(params: { skillsPrompt?: string; readToolName: string }) {
  return [
    "## Skills (mandatory)",
    "Before replying: scan <available_skills> <description> entries.",
    `- If exactly one skill clearly applies: read its SKILL.md at <location> with \`${params.readToolName}\`, then follow it.`,
    "- If multiple could apply: choose the most specific one, then read/follow it.",
    "- If none clearly apply: do not read any SKILL.md.",
    "Constraints: never read more than one skill up front; only read after selecting.",
    trimmed,
    "",
  ];
}
```

read @docs/openclaw-skill-discovery.md also

### Compatibility

Compatibility with multiple different models is wanted.

For the main and gemini should have specific 

Else use openrouter 

see @docs/openclaw-model-compatibility.md for more information of how it is done in typescript. You can use as basis for the python 





Step 3: Model selects the skill. The model itself performs the skill selection




## Main aim

Reimplementation of the ai repo src code in this new repo ai-harness under src/ with knowledge, improvements and features from the other repos references. For compatiblity use /v3/ endpoints.

Essentially most a rewrite of process_watchlists_request (still need the capture usage, conversation creation, saving to graphql etc)

## Tasks:
- Read reference repos so you understand how they work. See *.md for info also.
- Keep /v2/ implementation under deprecated folder perhaps ... so eventually (not now) can get rid 
- Focus only on the src code and evals i.e. ignore ui, deployment, cicd.
- Must be compatible with the current ai repo setup. That means it must be a websocket and MUST use ai's agent_v2.py
- The code MUST be written in python, only use Rust if high performance and well defined block
- from openclaw I like the ability to easily add skills in a folder & to work with multiple providers
- I want to code to be well structured and clean.
- The default llm the websocket should use should be gemini flash unless greater effort is needed
- No UI is needed
- Ultrathink. Think step by step.
- After coming up with a plan, rethink and see if you can make any improvements
- Create a diagram, mermaid.js of the code and how its structured after. This will help see if it structured well and if any improvements can be made 
- Some features to think about:
  - A main agent loop (that should be like claude code)
  - System prompt should take soul, skills, channels etc
  - each llm call should be capture for usage (use existing code from ai-main repo)
  - memory system using the skill and can also search the memories graphql if needed 
  - skills
  - tools (see the tools above you need to implement)
  - post hooks for compact, auto dream

- For evals we can use langfuse and deepeval (the aim to check the systematically tests how well the agent answers financial questions. It measures correctness by comparing the agent's responses against expected answers.)


## Telemetry (environment variables)

Optional backends initialize in FastAPI lifespan via `setup_telemetry(telemetry_config)`. If DSN/keys are empty, initialization is a no-op.

| Variable | Purpose | Default |
| -------- | ------- | ------- |
| `SENTRY_DSN` | Sentry project DSN | _empty_ (disabled) |
| `POSTHOG_API_KEY` | PostHog project API key | _empty_ (disabled) |
| `POSTHOG_HOST` | PostHog ingest URL | `https://app.posthog.com` |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key | _empty_ (disabled) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key | _empty_ |
| `LANGFUSE_HOST` | Langfuse API host | `https://cloud.langfuse.com` |
| `TELEMETRY_REDACT_PROMPTS` | When `1`/`true`, redact large prompt/tool payloads in captures (structure preserved; long strings → length + sha256 prefix) | `1` |
| `TELEMETRY_REDACT_TOOL_ARGS` | When `1`/`true`, redact tool argument values (names/keys kept) | `1` |
| `TELEMETRY_SAMPLE_RATE` | Sentry traces sample rate `0.0`–`1.0` | `1.0` |

Emails and `Authorization` / bearer patterns in strings are scrubbed on every capture regardless of the redact flags. Set `TELEMETRY_REDACT_PROMPTS=0` only in trusted environments if raw prompts are required.

PostHog events use JWT `sub` as `distinct_id`. Langfuse records one root trace per chat or automation turn (`run_chat` / `run_automation`), with child spans for each provider completion and tool execution.

## Clarification

- Clarify the project structure before beginning
- MUST Consider that a single implementation might be too much for a single turn, break down the plan into different plan markdown files so we can focus on specific parts e.g. skeleton + schema improvement, agent run loop, skills, tools, post hooks etc. Think step by step on this part (multiple plan files)


Ask 10 - 20 clarification questions so we get the implementation correct. Get confirmation of the project structure before continuing.
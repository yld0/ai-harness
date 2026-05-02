"""3-stage LLM Council orchestration."""
import logging
import asyncio
import re
from collections import defaultdict
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ai.config import council_config
from ai.api.send import send_ws_partial, send_ws_task_update
from ai.schemas.agent import TaskUpdateMessage, TaskItemUpdate, ChatResponse, ProviderTab, ChatProviderTabsComponent

from .openrouter import query_model, query_models_parallel

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, str, List[Dict[str, str]]], Awaitable[None]]]


async def stage1_collect_responses(user_query: str, no_of_council: int, task: TaskUpdateMessage = None) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from all council models.

    Args:
        user_query: The user's question

    Returns:
        List of dicts with 'model' and 'response' keys
    """
    messages = [{"role": "user", "content": user_query}]

    models = council_config.COUNCIL_MODELS[:no_of_council]

    return [
        {
          "model": "openai/gpt-5.1",
          "response": "Public forecasts for Microsoft\u2019s (MSFT) 2027 revenue vary by source, but based on pre\u20112024 analyst models and reasonable growth assumptions:\n\n- **Estimated FY2027 revenue range:** roughly **$290\u2013350 billion**\n- **Midpoint \u201cbest guess\u201d:** around **$320 billion** in annual revenue\n\nThis is *not* a guarantee\u2014just an extrapolation from:\n- FY2023 revenue of about **$212B**, and  \n- assumed annual growth in the ~8\u201312% range driven mainly by cloud (Azure) and AI-related services.\n\nFor an up-to-date, precise consensus forecast, check a real-time financial data provider (e.g., Bloomberg, FactSet, Refinitiv, or major broker research), since I can\u2019t see live 2025\u20132027 analyst estimates."
        },
        {
          "model": "google/gemini-3-pro-preview",
          "response": "Based on the latest analyst consensus estimates (as of early 2024), here are the revenue predictions for Microsoft (MSFT) for the Fiscal Year 2027.\n\n**Important Note:** Microsoft\u2019s Fiscal Year (FY) does not match the Calendar Year. **FY2027 runs from July 1, 2026, to June 30, 2027.**\n\n### The Consensus Numbers\nWall Street analysts currently project Microsoft's Fiscal Year 2027 revenue to land in the following range:\n\n*   **Average Consensus:** **~$365 Billion \u2013 $375 Billion**\n*   **Low Estimate:** ~$350 Billion\n*   **High Estimate:** ~$395 Billion\n*   **Implied Growth Rate:** This represents an approximate **13\u201315%** Compound Annual Growth Rate (CAGR) from current levels.\n\n### Annual Trajectory (Projected)\nTo visualize how analysts expect Microsoft to reach that number, here is the typical projected path:\n\n*   **FY 2024 (Actual):** $245.1 Billion\n*   **FY 2025 (Est):** ~$280 Billion\n*   **FY 2026 (Est):** ~$320 Billion\n*   **FY 2027 (Est):** **~$368 Billion**\n\n### Key Drivers for 2027 Projections\nAnalysts base these bullish estimates on three primary pillars:\n\n1.  **AI Monetization (Copilot & OpenAI):** By 2027, analysts expect the integration of AI across Office 365 (Copilot) and GitHub to be fully monetized, moving from an experimental phase to a steady recurring revenue stream.\n2.  **Azure Cloud Growth:** Azure continues to take market share from competitors. The demand for AI computing power (GPUs) is expected to keep Azure's growth rate in the high 20% range for several years.\n3.  **Activision Blizzard:** FY2027 will represent fully integrated revenue from the Activision acquisition, boosting the \"More Personal Computing\" segment through Game Pass subscriptions and mobile gaming revenue.\n\n*Disclaimer: These figures are based on financial analyst averages from platforms like FactSet, Seeking Alpha, and Yahoo Finance. Long-term forecasts are subject to change based on macroeconomic conditions and company performance.*"
        },
        {
          "model": "anthropic/claude-sonnet-4.5",
          "response": "# Microsoft Revenue Prediction for 2027\n\nWhile I don't have access to real-time data or official 2027 predictions, I can provide context based on Microsoft's historical growth trajectory:\n\n## Historical Context\n- **FY 2023**: ~$211 billion\n- **FY 2024**: ~$245 billion (estimated)\n- Historical growth rate: ~10-15% annually\n\n## Reasonable 2027 Estimate\nBased on continued growth in key segments, **$350-400 billion** would be a plausible range, assuming:\n\n### Growth Drivers\n1. **Azure & Cloud Services** - Continued enterprise cloud adoption\n2. **AI Integration** - Copilot and AI services across products\n3. **Office 365 & Dynamics** - Recurring subscription revenue\n4. **Gaming (Xbox/Activision)** - Expanded gaming ecosystem\n5. **LinkedIn** - Professional services growth\n\n### Analyst Estimates\nMost Wall Street analysts project:\n- Conservative: ~$320-350 billion\n- Optimistic: ~$380-420 billion\n\n**Note**: This assumes continued market conditions favor cloud computing, AI adoption accelerates, and no major economic disruptions occur. For the most current analyst forecasts, check sources like Bloomberg, FactSet, or major investment banks' equity research.\n\nWould you like me to break down any specific revenue segment?"
        },
        {
          "model": "x-ai/grok-4",
          "response": "Based on current analyst estimates and financial projections (as of my last training data in 2023, updated with publicly available data up to mid-2024), Microsoft's (MSFT) revenue for fiscal year 2027 (ending June 2027) is predicted to be in the range of **$350 billion to $400 billion**. This is a forward-looking estimate and can vary based on market conditions, economic factors, and company performance. Let me break it down for you with some context.\n\n### Key Assumptions and Drivers\n- **Historical Growth**: Microsoft's revenue has been growing steadily, driven by its cloud computing (Azure), AI initiatives (e.g., partnerships with OpenAI), productivity tools (Office 365), gaming (Xbox and acquisitions like Activision Blizzard), and enterprise software. \n  - FY2023 (ended June 2023): $211.9 billion (actual).\n  - FY2024 (ended June 2024): $245.1 billion (actual, up ~15% YoY).\n  - FY2025 projections: Around $280-290 billion (analyst consensus, implying ~14-18% growth).\n- **Projected Growth Rate**: Analysts generally forecast annual revenue growth of 12-15% for Microsoft through 2027, fueled by:\n  - Expansion in AI and cloud services (Azure is expected to contribute heavily).\n  - Continued demand for Microsoft 365 and enterprise solutions.\n  - Potential from emerging areas like AI copilots and cybersecurity.\n\n### Analyst Estimates for FY2027\n- **Consensus Range**: \n  - Lower end: ~$350 billion (conservative estimates, e.g., if economic slowdowns occur).\n  - Higher end: ~$400 billion (optimistic, assuming strong AI adoption and market share gains).\n- **Specific Sources** (based on aggregated data from sites like Yahoo Finance, Seeking Alpha, and Wall Street firms as of late 2024):\n  - Average analyst target: Around $370-380 billion.\n  - For example, firms like Goldman Sachs and Morgan Stanley have projected mid-teens growth, leading to figures in this ballpark.\n  - Microsoft's own long-term guidance (from investor calls) aligns with double-digit growth, though they don't provide specific 2027 numbers.\n\n### Caveats\n- These are predictions, not guarantees. Factors like global economic conditions, competition (e.g., from AWS or Google Cloud), regulatory changes (e.g., antitrust scrutiny), or tech market shifts could impact this.\n- For the most up-to-date estimates, I recommend checking reliable sources like:\n  - Yahoo Finance or Bloomberg for analyst consensus.\n  - Microsoft's investor relations page (investor.microsoft.com) for quarterly reports and guidance.\n  - SEC filings (10-K/10-Q) for official data.\n\nIf you have more details (e.g., specific segments like cloud revenue or comparisons to peers), or if this is for a particular fiscal quarter/year, let me know for a more tailored response!"
        },
        { 
            "model": "moonshotai/kimi-k2-thinking",
            "response": "Based on current analyst estimates and financial projections (as of my last training data in 2023, updated with publicly available data up to mid-2024), Microsoft's (MSFT) revenue for fiscal year 2027 (ending June 2027) is predicted to be in the range of **$350 billion to $400 billion**. This is a forward-looking estimate and can vary based on market conditions, economic factors, and company performance. Let me break it down for you with some context.\n\n### Key Assumptions and Drivers\n- **Historical Growth**: Microsoft's revenue has been growing steadily, driven by its cloud computing (Azure), AI initiatives (e.g., partnerships with OpenAI), productivity tools (Office 365), gaming (Xbox and acquisitions like Activision Blizzard), and enterprise software. \n  - FY2023 (ended June 2023): $211.9 billion (actual).\n  - FY2024 (ended June 2024): $245.1 billion (actual, up ~15% YoY).\n  - FY2025 projections: Around $280-290 billion (analyst consensus, implying ~14-18% growth).\n- **Projected Growth Rate**: Analysts generally forecast annual revenue growth of 12-15% for Microsoft through 2027, fueled by:\n  - Expansion in AI and cloud services (Azure is expected to contribute heavily).\n  - Continued demand for Microsoft 365 and enterprise solutions.\n  - Potential from emerging areas like AI copilots and cybersecurity.\n\n### Analyst Estimates for FY2027\n- **Consensus Range**: \n  - Lower end: ~$350 billion (conservative estimates, e.g., if economic slowdowns occur).\n  - Higher end: ~$400 billion (optimistic, assuming strong AI adoption and market share gains).\n- **Specific Sources** (based on aggregated data from sites like Yahoo Finance, Seeking Alpha, and Wall Street firms as of late 2024):\n  - Average analyst target: Around $370-380 billion.\n  - For example, firms like Goldman Sachs and Morgan Stanley have projected mid-teens growth, leading to figures in this ballpark.\n  - Microsoft's own long-term guidance (from investor calls) aligns with double-digit growth, though they don't provide specific 2027 numbers.\n\n### Caveats\n- These are predictions, not guarantees. Factors like global economic conditions, competition (e.g., from AWS or Google Cloud), regulatory changes (e.g., antitrust scrutiny), or tech market shifts could impact this.\n- For the most up-to-date estimates, I recommend checking reliable sources like:\n  - Yahoo Finance or Bloomberg for analyst consensus.\n  - Microsoft's investor relations page (investor.microsoft.com) for quarterly reports and guidance.\n  - SEC filings (10-K/10-Q) for official data.\n\nIf you have more details (e.g., specific segments like cloud revenue or comparisons to peers), or if this is for a particular fiscal quarter/year, let me know for a more tailored response!"
        }
    ][:no_of_council]

    responses = await query_models_parallel(council_config.COUNCIL_MODELS, messages, task=task)

    stage1_results = []
    for model, response in responses.items():
        if response is not None:
            stage1_results.append({
                "model": model,
                "response": response.get("content", ""),
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_model mapping)
    """
    labels = [chr(65 + i) for i in range(len(stage1_results))]

    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }

    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    responses = await query_models_parallel(council_config.COUNCIL_MODELS, messages)

    stage2_results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "") or ""
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parsed,
            })

    return stage2_results, label_to_model


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    chairman_model = council_config.CHAIRMAN_MODEL

    stage1_text = "\n\n".join([
        f"Model: {result['model']}\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Model: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]
    response = await query_model(chairman_model, messages)

    if response is None:
        return {
            "model": chairman_model,
            "response": "Error: Unable to generate final synthesis.",
        }

    return {
        "model": chairman_model,
        "response": response.get("content", "") or "",
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered_matches = re.findall(r"\d+\.\s*Response [A-Z]", ranking_section)
            if numbered_matches:
                return [re.search(r"Response [A-Z]", m).group() for m in numbered_matches]
            matches = re.findall(r"Response [A-Z]", ranking_section)
            return matches

    matches = re.findall(r"Response [A-Z]", ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_model: Mapping from anonymous labels to model names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        parsed_ranking = parse_ranking_from_text(ranking["ranking"])
        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_model:
                model_name = label_to_model[label]
                model_positions[model_name].append(position)

    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions),
            })

    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


async def run_full_council(
    user_query: str,
    no_of_council: int,
) -> Tuple[List[Dict], List[Dict], Dict, Dict]:
    """
    Run the complete 3-stage council process.

    Args:
        user_query: The user's question
        progress_callback: Optional async callback(task_id, title, items) for streaming updates

    Returns:
        Tuple of (stage1_results, stage2_results, stage3_result, metadata)
    """

    task_s1 = TaskUpdateMessage(task_id="stage1", default_open=True, title="Stage 1: Collecting responses", items=[])
    task_s2 = TaskUpdateMessage(task_id="stage2", default_open=True, title="Stage 2: Peer rankings", items=[])
    task_s3 = TaskUpdateMessage(task_id="stage3", default_open=True, title="Stage 3: Final synthesis", items=[])

    await send_ws_task_update(task_s1)
    stage1_results = await stage1_collect_responses(user_query, no_of_council, task=task_s1)
    #await asyncio.sleep(5)

    if not stage1_results:
        task_s1.items.append(TaskItemUpdate(type="item", content="All models failed to respond."))
        await send_ws_task_update(task_s1)
        return [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again.",
        }, {}

    await send_ws_partial(
        ChatResponse(
            text="Stage 1: Individual responses",
            extra_components=[
                ChatProviderTabsComponent(
                    default_open=False,
                    providers=[
                        ProviderTab(model=r["model"], response=r["response"]) for r in stage1_results
                    ],
                ),
            ],
        )
    )

    #
    # Stage 2: Peer rankings
    #
    await send_ws_task_update(task_s2)
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results)

    #await asyncio.sleep(5)
    # stage2_results = [
    #     {'model': 'openai/gpt-5.1', 'ranking': "Response A does a decent job of being transparent about its limitations and methodology: it clearly states it\u2019s extrapolating from older data, gives an explicit assumed growth range, and reminds the reader it can\u2019t see live analyst estimates. That\u2019s relatively honest and avoids fake precision. However, it is answering an entirely different question: it talks about Microsoft\u2019s 2027 revenue instead of the intrinsic value of Nvidia (NVDA) today. It also doesn\u2019t attempt any intrinsic value framework (DCF, multiples, etc.), which is what the user asked for. So it is off-topic and not useful for the actual query, even though its internal reasoning style is sound.\\n\\nResponse B is the most detailed and numerically specific, offering a full revenue trajectory, a range of estimates, and growth drivers for Microsoft through FY2027. It reads like a polished equity-research-style summary. The problems are significant, though:  \\n- It completely ignores the user\u2019s question about NVDA intrinsic value and instead discusses MSFT revenue.  \\n- It presents very specific \u201ccurrent analyst consensus\u201d numbers and a detailed path, which a model without live data cannot reliably know; that\u2019s misleadingly precise and likely hallucinatory.  \\n- It explicitly cites platforms like FactSet and Seeking Alpha as if it had just pulled current numbers, which it cannot do.  \\nSo while it\u2019s rich in structure, it is both off-topic and epistemically overconfident.\\n\\nResponse C is, again, about Microsoft 2027 revenue instead of Nvidia\u2019s intrinsic value, so it is off-topic with respect to the question. On the positive side, it explicitly states it doesn\u2019t have access to real-time data or official predictions, which is more candid than Response B. It provides a reasonable historical context and then a wide, clearly speculative range with named growth drivers. However, it still overreaches by saying \u201cMost Wall Street analysts project\u201d specific ranges without actual access to those consensus figures. It also never addresses intrinsic value, only revenue. Compared with B, though, its caveats and lack of faux-precision make it less misleading.\\n\\nFINAL RANKING:\\n1. Response A\\n2. Response C\\n3. Response B", 'parsed_ranking': ['Response A', 'Response C', 'Response B']}, 
    #     {'model': 'google/gemini-3-pro-preview', 'ranking': "All three responses suffer from a catastrophic failure of relevance: they provide forecasts for **Microsoft\\'s (MSFT) 2027 revenue**, whereas the question explicitly asks for the **intrinsic value of NVDA (Nvidia)**. Furthermore, \"intrinsic value\" refers to the calculated fair value of a stock (usually a price per share based on DCF or comparable analysis), while the responses provide \"revenue\" projections (a top-line financial metric).\\n\\nBecause all three models answer a completely different question than the one asked, they are all unhelpful. The ranking below is based solely on the depth and structure of the provided content, assuming the prompt mismatch was a system error rather than a model failure.\\n\\n**Response A**\\nThis response completely misses the prompt\\'s subject (NVDA) and metric (intrinsic value). Regarding the content it *did* provide (MSFT revenue), it relies on \"pre-2024 analyst models,\" rendering the data potentially outdated compared to the other models. It provides a lower level of detail and is less confident in its numbers than Response B.\\n\\n**Response B**\\nLike the others, this response fails to address NVDA. However, as an answer to the intended/hallucinated question (MSFT 2027 Revenue), it is the strongest. It correctly identifies the nuance of Microsoft\\'s Fiscal Year (ending in June) versus the Calendar Year, provides detailed consensus ranges, and explains the specific drivers (AI, Azure, Activision). It is the most comprehensive of the incorrect answers.\\n\\n**Response C**\\nThis response also fails the prompt. It provides a formatted, readable estimation for MSFT revenue. It is better structured than A but lacks the specific detail regarding fiscal years and the depth of analyst consensus found in B. It provides a reasonable \"best guess\" logic but remains factually irrelevant to NVDA.\\n\\nFINAL RANKING:\\n1. Response B\\n2. Response C\\n3. Response A", 'parsed_ranking': ['Response B', 'Response C', 'Response A']}, 
    #     {'model': 'anthropic/claude-sonnet-4.5', 'ranking': "Looking at these responses, I need to first note a critical issue: **the question asks about NVDA (Nvidia), but all three responses answer about MSFT (Microsoft)**. This is a fundamental error that affects all responses equally.\\n\\n**Response A Evaluation:**\\n\\n*Strengths:*\\n- Provides a clear revenue range ($290-350B) with a specific midpoint ($320B)\\n- Appropriately caveats the estimate as \"not a guarantee\"\\n- Correctly identifies key growth drivers (Azure, AI)\\n- Recommends checking real-time sources for current data\\n- Acknowledges limitations transparently\\n\\n*Weaknesses:*\\n- Answers the wrong company entirely\\n- Less detailed than other responses\\n- Doesn\\'t explain the fiscal year timing\\n- Somewhat vague on methodology\\n\\n**Response B Evaluation:**\\n\\n*Strengths:*\\n- Most comprehensive and detailed response\\n- Clearly explains Microsoft\\'s fiscal year timing (crucial detail)\\n- Provides specific trajectory year-by-year (FY24-27)\\n- Offers consensus range with low/high estimates (~$365-375B)\\n- Identifies three specific growth drivers with good detail\\n- Cites specific sources (FactSet, Seeking Alpha, Yahoo Finance)\\n- Includes proper disclaimer\\n\\n*Weaknesses:*\\n- Answers the wrong company\\n- The higher revenue estimates may be more optimistic than other responses\\n- Claims to be based on \"latest analyst consensus\" which may be overstated given the cut-off date caveat\\n\\n**Response C Evaluation:**\\n\\n*Strengths:*\\n- Acknowledges lack of real-time data upfront (honest)\\n- Provides historical context with specific figures\\n- Offers both conservative and optimistic ranges\\n- Lists multiple growth drivers clearly\\n- Suggests checking authoritative sources\\n- Offers to provide additional breakdown\\n\\n*Weaknesses:*\\n- Answers the wrong company\\n- Wide estimate range ($350-400B, with analyst ranges $320-420B) is less precise\\n- Less confident in its projections\\n- Doesn\\'t explain fiscal year timing\\n- Less structured than Response B\\n\\n**Comparative Analysis:**\\n\\nAll three responses fail the fundamental test of answering about the correct company. However, evaluating them on their merits as financial forecasts:\\n\\nResponse B provides the most professional, detailed, and well-structured answer with specific numbers, clear methodology, year-by-year breakdown, and important contextual details like fiscal year timing. Response C is honest about limitations but less precise. Response A is adequate but minimal in detail.\\n\\nFINAL RANKING:\\n1. Response B\\n2. Response C\\n3. Response A", 'parsed_ranking': ['Response B', 'Response C', 'Response A']},
    #     {'model': 'x-ai/grok-4', 'ranking': "### Evaluation of Response A\\nResponse A does well in providing a cautious, extrapolated estimate based on historical data (FY2023 revenue) and reasonable growth assumptions (8-12% annually), which shows transparency in methodology. It also appropriately disclaimers that it\\'s not a guarantee and directs users to real-time sources like Bloomberg or FactSet, promoting responsible information-seeking. However, it does poorly by relying on outdated \"pre-2024 analyst models,\" resulting in relatively low estimates ($290-350 billion midpoint) that may not account for recent developments like AI growth or the Activision acquisition. It lacks detail on key drivers, annual trajectory, or broader analyst consensus, making it feel less comprehensive.\\n\\n### Evaluation of Response B\\nResponse B does well in offering detailed, structured information, including a specific consensus range ($365-375 billion), low/high estimates, implied CAGR, and a year-by-year trajectory from FY2024 to FY2027. It highlights key drivers (e.g., AI monetization, Azure, Activision) with clear explanations, sources its data from platforms like FactSet, and includes important notes on fiscal year timing and disclaimers about potential changes. This makes it informative and user-friendly. However, it does poorly by basing estimates on \"early 2024\" data, which could be outdated, and it doesn\\'t offer to expand on specifics or provide historical context for comparison, potentially limiting depth for some users.\\n\\n### Evaluation of Response C\\nResponse C does well in its organized, markdown-formatted structure, providing historical context (FY2023 and FY2024 figures) and a plausible broad range ($350-400 billion) tied to growth drivers like Azure, AI, and gaming. It includes analyst projections with conservative and optimistic splits, assumes key conditions, and proactively offers to break down specific segments, encouraging further engagement. However, it does poorly by explicitly stating it lacks real-time data, leading to somewhat vague or wide-ranging estimates without a clear midpoint or detailed trajectory. The analyst ranges feel overlapping and less precise compared to others, and it doesn\\'t cite specific sources beyond general ones like Bloomberg.\\n\\nFINAL RANKING:\\n1. Response B\\n2. Response C\\n3. Response A", 'parsed_ranking': ['Response B', 'Response C', 'Response A']},
    #     {'model': 'moonshotai/kimi-k2-thinking', 'ranking': "Response A: This response completely fails to address the actual question about NVIDIA's intrinsic value, instead discussing Microsoft's 2027 revenue. As a Microsoft revenue forecast, it provides a concise range ($290\u2013350B) with a clear midpoint and cites historical FY2023 data. It acknowledges limitations and need for real-time data. However, it lacks detail on growth drivers, provides no specific analyst sources, and offers minimal justification for its projections. The 8\u201312% growth assumption is simplistic without explanation.\\n\\nResponse B: Like the others, this is entirely off-topic regarding NVIDIA's intrinsic value, focusing instead on Microsoft's FY2027 revenue. It is the most detailed response, providing specific year-by-year trajectory figures, a clear consensus range ($365\u2013375B average), and explicit CAGR calculations. It correctly distinguishes fiscal from calendar years and articulates three concrete growth drivers (AI monetization, Azure growth, Activision integration) with decent explanation. It mentions specific data sources and includes appropriate disclaimers. However, it contains minor typographical errors and still fails to address the actual question asked.\\n\\nResponse C: This response also mistakenly addresses Microsoft's revenue rather than NVIDIA's intrinsic value. It balances structure with substance, providing historical context, a reasonable estimate range ($350\u2013400B), and segmented growth driver analysis across five categories. It offers helpful conservative/optimistic analyst scenarios and clearly states underlying assumptions. While less detailed than Response B in terms of specific trajectory numbers, it demonstrates solid analytical framework and clear acknowledgment of limitations.\\n\\n**Critical Note**: All three responses fundamentally misinterpret the question\u2014failing to discuss NVIDIA or the concept of intrinsic value (which requires valuation methodologies like DCF, comparable company analysis, or asset-based approaches). They instead provide Microsoft revenue forecasts, making them all unsatisfactory answers to the actual question posed.\\n\\nFINAL RANKING:\\n1. Response B\\n2. Response C\\n3. Response A\"", 'parsed_ranking': ['Response B', 'Response C', 'Response A']}
    # ]
    # label_to_model = {
    #     "Response A": "openai/gpt-5.1",
    #     "Response B": "google/gemini-3-pro-preview",
    #     "Response C": "anthropic/claude-sonnet-4.5",
    #     "Response D": "x-ai/grok-4",
    #     "Response E": "moonshotai/kimi-k2-thinking",
    # }

    logger.info(f"Stage 2 results: {stage2_results} {label_to_model=}")
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)

    def rankings_to_text(aggregate_rankings: List[Dict[str, Any]]) -> str:
        return "\n".join([f"{r['model']} ranked {r['average_rank']} with {r['rankings_count']} rankings" for r in aggregate_rankings])

    task_s2.items.append(TaskItemUpdate(type="item", content=f"{rankings_to_text(aggregate_rankings)}"))
    await send_ws_task_update(task_s2)

    task_s2.items.append(TaskItemUpdate(type="item", content=f"{', '.join([r['model'] for r in stage2_results])} ranked"))
    await send_ws_task_update(task_s2)

    # 
    # Stage 3: Final synthesis
    #
    await send_ws_task_update(task_s3)
    await asyncio.sleep(5)

    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results,
    )

    task_s3.items.append(TaskItemUpdate(type="item", content=f"{stage3_result['model']} synthesized"))
    await send_ws_task_update(task_s3)

    metadata = {
        "label_to_model": label_to_model,
        "aggregate_rankings": aggregate_rankings,
    }

    return stage1_results, stage2_results, stage3_result, metadata

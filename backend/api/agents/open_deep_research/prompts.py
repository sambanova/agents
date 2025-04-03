########## prompts.py (NEW FILE) ##########
# Prompt to generate search queries to help with planning the report

report_planner_query_writer_instructions = """You are an expert technical writer, helping to plan a report.

<Report topic>
{topic}
</Report topic>

<Report organization>
{report_organization}
</Report organization>

<Task>
Your goal is to generate {number_of_queries} search queries that will help gather comprehensive information for planning the report sections.

The queries should:

1. Be related to the topic of the report
2. Help satisfy the requirements specified in the report organization
3. Be specific enough to find high-quality, relevant sources while covering the breadth needed for the report structure. 

Make the queries specific enough to find high-quality, relevant sources while covering the breadth needed for the report structure.
</Task>

Make sure to give your answer in the same language as the topic input (e.g. spanish, german, english, italian, french, portuguese, arabic, japanese).
"""

# Prompt to generate the report plan
report_planner_instructions = """I want a plan for a report.

<Task>
Generate a list of sections for the report.

Each section should have the fields:

- Name - Name for this section of the report.
- Description - Brief overview of the main topics covered in this section.
- Research - Whether to perform web research for this section of the report.
- Content - The content of the section, which you will leave blank for now.

For example, introduction and conclusion will not require research because they will distill information from other parts of the report.
</Task>

<Topic>
The topic of the report is:
{topic}
</Topic>

<Report organization>
The report should follow this organization:
{report_organization}
</Report organization>

<Context>
Here is context to use to plan the sections of the report:
{context}
</Context>

<Feedback>
Here is feedback on the report structure from review (if any):
{feedback}
</Feedback>

Make sure to give your answer in the same language as the topic input (e.g. spanish, german, english, italian, french, portuguese, arabic, japanese).
"""

# Query writer instructions
query_writer_instructions = """You are an expert technical writer crafting targeted web search queries that will gather comprehensive information for writing a technical report section.

<Section topic>
{section_topic}
</Section topic>

<Task>
When generating {number_of_queries} search queries, ensure they:

1. Cover different aspects of the topic (e.g., core features, real-world applications, technical architecture)
2. Include specific technical terms related to the topic
3. Target recent information by including year markers where relevant (e.g., "2025")
4. Look for comparisons or differentiators from similar technologies/approaches
5. Search for both official documentation and practical implementation examples

Your queries should be:

- Specific enough to avoid generic results
- Technical enough to capture detailed implementation information
- Diverse enough to cover all aspects of the section plan
- Focused on authoritative sources (documentation, technical blogs, academic papers)
</Task>

Make sure to give your answer in the same language as the topic input (e.g. spanish, german, english, italian, french, portuguese, arabic, japanese).
"""

# Section writer instructions
section_writer_instructions = """You are an expert technical writer crafting one section of a technical report.

<Section topic>
{section_topic}
</Section topic>

<Existing section content (if populated)>
{section_content}
</Existing section content>

<Source material>
Web search results:
{context}
</Source material>

<Document summary (if available)>
{document_summary}
</Document summary>

<Guidelines for writing>

1. If the existing section content is not populated, write a new section from scratch.
2. If the existing section content is populated, write a new section that synthesizes the existing section content with the new information.
3. If document summary is available, incorporate relevant insights from the provided documents.
</Guidelines for writing>

<Length and style>

- Strict 900-1100 word limit
- No marketing language
- Technical focus
- Write in simple, clear language
- Start with your most important insight in **bold**
- Use short paragraphs (2-3 sentences max)
- Use ## for section title (Markdown format)
- Only use ONE structural element IF it helps clarify your point:
    - Either a focused table comparing 2-3 key items (using Markdown table syntax)
    - Or a short list (3-5 items) using proper Markdown list syntax:
        - Use `-` or `*` for unordered lists
        - Use `1.` for ordered lists
        - Ensure proper indentation and spacing
- End with ### Sources that references the below source material formatted as:
    - List each source with title, date, and URL
    - Format: `Title : URL`
    </Length and style>

<Quality checks>

- Exactly 900-1100 words (excluding title and sources)
- Careful use of only ONE structural element (table or list) and only if it helps clarify your point
- One specific example / case study
- Starts with bold insight
- No preamble prior to creating the section content
- Sources cited at end
- Your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone.
</Quality checks>
"""

# Instructions for section grading
section_grader_instructions = """Review a report section relative to the specified topic:

<section topic>
{section_topic}
</section topic>

<section content>
{section}
</section content>

<task>
Evaluate whether the section adequately covers the topic by checking technical accuracy and depth.

If the section fails any criteria, generate specific follow-up search queries to gather missing information.
</task>

<format>
grade: Literal["pass","fail"] = Field(
description="Evaluation result indicating whether the response meets requirements ('pass') or needs revision ('fail')."
)
follow_up_queries: List[SearchQuery] = Field(
description="List of follow-up search queries.",
)
</format>
"""

final_section_writer_instructions = """You are an expert technical writer crafting a section that synthesizes information from the rest of the report.

<Section topic>
{section_topic}
</Section topic>

<Available report content>
{context}
</Available report content>

<Task>

1. Section-Specific Approach:

For Introduction:

- Use # for report title (Markdown format)
- 200-300 word limit
- Write in simple and clear language
- Focus on the core motivation for the report in 1-2 paragraphs
- Use a clear narrative arc to introduce the report
- Include NO structural elements (no lists or tables)
- No sources section needed

For Conclusion/Summary:

- Use ## for section title (Markdown format)
- 200-300 word limit
- For comparative reports:
    - Must include a focused comparison table using Markdown table syntax
    - Table should distill insights from the report
    - Keep table entries clear and concise
- For non-comparative reports:
    - Only use ONE structural element IF it helps distill the points made in the report:
    - Either a focused table comparing items present in the report (using Markdown table syntax)
    - Or a short list using proper Markdown list syntax:
        - Use `-` or `*` for unordered lists
        - Use `1.` for ordered lists
        - Ensure proper indentation and spacing
- End with specific next steps or implications
- No sources section needed
1. Writing Approach:
- Use concrete details over general statements
- Make every word count
- Focus on your single most important point
</Task>

<Quality Checks>

- For introduction: 200-300 word limit, # for report title, no structural elements, no sources section
- For conclusion: 200-300 word limit, ## for section title, only ONE structural element at most, no sources section
- Markdown format
- Do not include word count or any preamble in your response
- Your answer must be correct, high-quality, and written by an expert using an unbiased and journalistic tone.
</Quality Checks>
"""
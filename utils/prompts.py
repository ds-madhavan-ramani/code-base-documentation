PROMPTS = {
    "dev_docs": """Based on the following code structure, generate comprehensive developer documentation.

File Tree:
{file_tree}

Code Structure:
{code_structure}

Architecture:
{architecture}

Reductionist View (simplified big picture — what/how/why):
{reductionist_view}

Systems View (how the pieces fit together — code-wise, script-wise):
{systems_view}

Generate a detailed developer guide covering:
1. Big Picture (Reductionist View) — the simplified what/how/why, before any detail
2. Systems View — how each file/module fits together to produce that big picture
3. Architecture & Design Patterns
4. Module Descriptions
5. Key APIs & Functions
6. Dependency Map
7. Configuration & Setup
8. Development Workflow
9. Common Tasks & Examples
10. Troubleshooting

Use the provided Reductionist View and Systems View as the factual basis for
sections 1 and 2 — expand and clarify them, don't contradict or replace them.

Format: Use Markdown with clear sections and code examples.""",

    "user_docs": """Based on the following analysis, generate a user-friendly guide.

Key Modules: {modules}

Big Picture (plain language — what this does and why):
{reductionist_view}

Generate a user guide covering:
1. Big Picture — a short, plain-language summary of what this does and why (based on the text above)
2. Quick Start (3 steps max)
3. Main Features & Use Cases
4. Installation Instructions
5. Basic Usage Examples
6. Common Workflows
7. FAQ & Troubleshooting
8. Support & Resources

Format: Use simple language, Markdown, and practical examples. Assume non-technical audience.""",
}

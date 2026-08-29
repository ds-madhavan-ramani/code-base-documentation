PROMPTS = {
    "dev_docs": """Based on the following code structure, generate comprehensive developer documentation.

File Tree:
{file_tree}

Code Structure:
{code_structure}

Architecture:
{architecture}

Generate a detailed developer guide covering:
1. Project Overview & Purpose
2. Architecture & Design Patterns
3. Module Descriptions
4. Key APIs & Functions
5. Dependency Map
6. Configuration & Setup
7. Development Workflow
8. Common Tasks & Examples
9. Troubleshooting

Format: Use Markdown with clear sections and code examples.""",

    "user_docs": """Based on the following analysis, generate a user-friendly guide.

Key Modules: {modules}

Generate a user guide covering:
1. Quick Start (3 steps max)
2. Main Features & Use Cases
3. Installation Instructions
4. Basic Usage Examples
5. Common Workflows
6. FAQ & Troubleshooting
7. Support & Resources

Format: Use simple language, Markdown, and practical examples. Assume non-technical audience.""",
}

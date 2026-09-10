import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from core.ollama_client import OllamaClient
from core.odysseus_ollama_provider import health_check as odysseus_provider_health_check
from core.code_parser import CodeParser
from core.doc_generator import DocumentationGenerator

def test_pipeline():
    print("\n=== Integration Test ===\n")
    
    print("1️⃣  Testing Ollama...")
    ollama = OllamaClient("http://localhost:11434")
    assert ollama.health_check(), "Ollama not responding"
    models = ollama.list_models()
    print(f"   ✓ Ollama healthy, {len(models)} models available")
    if models:
        for model in models[:3]:
            print(f"     - {model}")
    
    print("\n2️⃣  Testing Odysseus (via the local Ollama provider)...")
    # Odysseus Harness runs in-process (core/odysseus_analysis_agent.py) and
    # is only as healthy as the Ollama server it's been redirected to.
    if odysseus_provider_health_check():
        print("   ✓ Odysseus's Ollama backend is healthy")
    else:
        print("   ⚠️  Ollama not responding — Odysseus analysis will use the lightweight fallback")
    
    print("\n3️⃣  Testing Code Parser...")
    sample_py = """import os
from pathlib import Path

def hello_world():
    return 'Hello'

class MyClass:
    def method(self):
        pass
"""
    parser = CodeParser(".")
    structure = parser.extract_structure(sample_py, "py")
    assert "hello_world" in structure["functions"], "Parser failed to extract functions"
    assert "MyClass" in structure["classes"], "Parser failed to extract classes"
    print(f"   ✓ Parser working")
    print(f"     - Functions: {structure['functions']}")
    print(f"     - Classes: {structure['classes']}")
    
    print("\n4️⃣  Testing Ollama generation...")
    response = ollama.generate(
        "qwen2.5-coder:7b",
        "Write a Python hello world function in 20 words:",
        context_length=256,
        temperature=0.5
    )
    assert len(response) > 0, "Ollama generation failed"
    print(f"   ✓ Generated: {response[:80]}...")
    
    print("\n5️⃣  Testing Doc Generator...")
    doc_gen = DocumentationGenerator("./test_output")
    test_md = "# Test\n\n## Section\n\nThis is a test.\n\n```python\nprint('hello')\n```"
    html = doc_gen.markdown_to_html(test_md, "Test Doc")
    assert ("<h1" in html or "DOCTYPE" in html), f"HTML generation failed. Got: {html[:150]}"
    assert len(html) > 50, "HTML output too short"
    assert "<h2" in html or "<h2>" in html, "HTML generation failed for h2"
    assert "print" in html, "HTML generation failed for code"
    print("   ✓ HTML generation working")
    
    print("\n✅ All tests passed!\n")
    return True

if __name__ == "__main__":
    try:
        test_pipeline()
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)

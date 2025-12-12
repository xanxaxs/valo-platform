"""
Test LLM Analysis.

Tests the Local LLM connection and match analysis.
"""

import sys
import asyncio
sys.stdout.reconfigure(encoding='utf-8')

# Setup path
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.database import SessionLocal
from src.db.models import Match
from src.ai.llm_client import LocalLLMClient, OllamaClient


async def test_llm_connection():
    """Test LLM server connection."""
    print("=" * 60)
    print("LLM Connection Test")
    print("=" * 60)
    
    # Try LM Studio first (default)
    print("\n[1] Testing LM Studio (localhost:1234)...")
    lm_studio = LocalLLMClient(
        base_url="http://localhost:1234/v1",
        model="local-model"
    )
    
    if await lm_studio.is_available():
        print("  -> LM Studio is AVAILABLE")
        return lm_studio, "lm_studio"
    else:
        print("  -> LM Studio is NOT available")
    
    # Try Ollama
    print("\n[2] Testing Ollama (localhost:11434)...")
    ollama = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.2:1b"
    )
    
    if await ollama.is_available():
        print("  -> Ollama is AVAILABLE")
        return ollama, "ollama"
    else:
        print("  -> Ollama is NOT available")
    
    print("\n[!] No LLM server found. Please start one of:")
    print("    - LM Studio: https://lmstudio.ai/")
    print("    - Ollama: https://ollama.ai/")
    return None, None


async def test_simple_chat(llm):
    """Test simple chat completion."""
    print("\n" + "=" * 60)
    print("Simple Chat Test")
    print("=" * 60)
    
    prompt = "Hello! Please respond with a brief greeting in Japanese."
    
    print(f"\nPrompt: {prompt}")
    print("\nWaiting for response...")
    
    response = await llm.chat(
        prompt=prompt,
        temperature=0.7,
        max_tokens=100
    )
    
    print(f"\nResponse: {response.content}")
    print(f"Model: {response.model}")
    print(f"Tokens: {response.tokens_used}")
    
    return response.content and "Error" not in response.content


async def test_coaching_prompt(llm):
    """Test coaching-style analysis prompt."""
    print("\n" + "=" * 60)
    print("Coaching Prompt Test")
    print("=" * 60)
    
    system_prompt = """あなたはValorantのプロコーチです。
チームのコミュニケーションを分析し、具体的で実践的なフィードバックを提供します。"""
    
    transcript = """
[0:15] Player1: 敵Aサイトにいるよ
[0:18] Player2: 了解、Bサイト行く
[0:25] Player3: スモーク炊いて
[0:30] Player1: ダメージ入った、Aショート
[0:35] Player2: カバー行く
"""
    
    prompt = f"""以下のValorantの試合中の会話を分析してください。

会話ログ:
{transcript}

分析ポイント:
1. 報告のタイミングと内容
2. チーム連携の効率

簡潔に評価してください（50文字以内）。"""
    
    print(f"\nSystem Prompt: {system_prompt[:50]}...")
    print(f"\nUser Prompt: {prompt[:100]}...")
    print("\nWaiting for response...")
    
    response = await llm.chat(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.7,
        max_tokens=200
    )
    
    print(f"\nResponse:\n{response.content}")
    print(f"\nTokens used: {response.tokens_used}")
    
    return response.content and "Error" not in response.content


async def test_full_match_analysis():
    """Test full match analysis with database."""
    print("\n" + "=" * 60)
    print("Full Match Analysis Test")
    print("=" * 60)
    
    session = SessionLocal()
    
    try:
        # Get latest match
        match = session.query(Match).order_by(Match.updated_at.desc()).first()
        
        if not match:
            print("No matches found in database")
            return False
        
        print(f"\nMatch: {match.match_id}")
        print(f"Map: {match.map_name}")
        print(f"Score: {match.ally_score}-{match.enemy_score}")
        
        # Import CoachService
        from src.ai.coach import CoachService
        
        # Check for LLM
        llm, llm_type = await test_llm_connection()
        if not llm:
            print("\nSkipping full analysis - no LLM available")
            return False
        
        print(f"\nInitializing CoachService with {llm_type}...")
        
        use_ollama = (llm_type == "ollama")
        
        coach = CoachService(
            session=session,
            llm_url="http://localhost:11434" if use_ollama else "http://localhost:1234/v1",
            llm_model="llama3.2:1b" if use_ollama else "local-model",
            use_ollama=use_ollama,
        )
        
        print("\nRunning match analysis (this may take a while)...")
        
        analysis = await coach.analyze_match(match.match_id)
        
        if analysis:
            print("\n" + "=" * 60)
            print("ANALYSIS RESULTS")
            print("=" * 60)
            print(f"\nMatch: {analysis.map_name} ({analysis.score})")
            print(f"Result: {analysis.result}")
            print(f"\nOverall Score: {analysis.overall_score}/100")
            print(f"Communication Rating: {analysis.communication_rating}")
            
            print(f"\nKey Issues:")
            for issue in analysis.key_issues:
                print(f"  - {issue}")
            
            print(f"\nStrengths:")
            for strength in analysis.strengths:
                print(f"  + {strength}")
            
            print(f"\nRound Feedbacks: {len(analysis.round_feedbacks)} rounds analyzed")
            
            return True
        else:
            print("Analysis failed")
            return False
            
    finally:
        session.close()


async def main():
    print("=" * 60)
    print("VALORANT TRACKER - LLM ANALYSIS TEST")
    print("=" * 60)
    
    # Test 1: Connection
    llm, llm_type = await test_llm_connection()
    
    if not llm:
        print("\n[FAILED] Cannot proceed without LLM server")
        print("\nTo test LLM analysis:")
        print("1. Install LM Studio or Ollama")
        print("2. Download a model (e.g., llama3.2, mistral)")
        print("3. Start the server")
        print("4. Run this script again")
        return
    
    # Test 2: Simple Chat
    print("\n")
    chat_ok = await test_simple_chat(llm)
    
    if not chat_ok:
        print("\n[FAILED] Simple chat test failed")
        return
    
    # Test 3: Coaching Prompt
    print("\n")
    coaching_ok = await test_coaching_prompt(llm)
    
    if not coaching_ok:
        print("\n[FAILED] Coaching prompt test failed")
        return
    
    # Test 4: Full Analysis
    print("\n")
    print("Running full match analysis...")
    await test_full_match_analysis()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


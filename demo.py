from app.agents.sample_analyzer.runner import run_sr_agent
import time

def demo_agent():
    print("==================================================")
    print("🤖 Plantifique AI Agent Demo — Vertex AI (Gemini 2.0 Flash) \n")
    print("==================================================")

    # SR 001 is a Tier 3 product (requires AI evaluation)
    print("\n--- TEST CASE 1: AI Evaluation (Tier 3 Product) ---")
    print("Sending SR '001' to LangGraph...")
    start_time = time.time()
    
    result_1 = run_sr_agent('001', threshold=70)
    
    elapsed = round(time.time() - start_time, 2)
    print(f"✅ LangGraph route complete ({elapsed}s)")
    print(f"Product Tier: {result_1['tier']}")
    print(f"AI Gemini Score: {result_1['llm_score']}/100")
    print(f"AI Gemini Reasoning: {result_1['llm_reasoning']}")
    print(f"Final Decision: {result_1['final_decision']}")

    # SR 003 is a Tier 1 product (bypass AI, flag for human internal review)
    print("\n\n--- TEST CASE 2: Internal Bypass (Tier 1 Product) ---")
    print("Sending SR '003' to LangGraph...")
    start_time = time.time()
    
    result_2 = run_sr_agent('003', threshold=70)
    
    elapsed = round(time.time() - start_time, 2)
    print(f"✅ LangGraph route complete ({elapsed}s) (Notice how fast this is because it bypassed Vertex AI)")
    print(f"Product Tier: {result_2['tier']}")
    print(f"AI Gemini Score: {result_2['llm_score']}")
    print(f"Final Decision: {result_2['final_decision']}")
    print(f"Reason: {result_2['decision_reason']}")

    # SR 004 is a Tier 4 product but the creator has $0 GMV and low post rate
    print("\n\n--- TEST CASE 3: AI Rejection (Fails Performance Criteria) ---")
    print("Sending SR '004' (Mango Cleansing Balm) to LangGraph...")
    start_time = time.time()
    
    result_3 = run_sr_agent('004', threshold=70)
    
    elapsed = round(time.time() - start_time, 2)
    print(f"✅ LangGraph route complete ({elapsed}s)")
    print(f"Product Tier: {result_3['tier']}")
    print(f"AI Gemini Score: {result_3['llm_score']}/100")
    print(f"AI Gemini Reasoning: {result_3['llm_reasoning']}")
    print(f"Final Decision: {result_3['final_decision']}")
    print(f"Reason: {result_3['decision_reason']}")
    print("\n==================================================")

if __name__ == "__main__":
    demo_agent()

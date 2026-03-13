---
name: nus-knowledge-qa
description: Answers NUS campus questions using RAG over scraped NUS knowledge base via WaveSpeed AI
version: 1.0.0
user-invocable: true
agent: knowledge_agent
powered_by: WaveSpeed AI + ChromaDB
---

# NUS Knowledge Q&A Skill

## Description
This skill provides intelligent Q&A about NUS using a RAG pipeline:
1. Hybrid retrieval: ChromaDB semantic search + BM25 keyword search
2. Reciprocal Rank Fusion for result merging
3. WaveSpeed AI generates streaming answers with source citations

## Knowledge Sources
- NUS Graduate Studies programs (nusgs.nus.edu.sg)
- NUSMods module information (api.nusmods.com)
- NUS Registrar academic policies
- NUS Career & Professional Development (CFG)
- NUS OSA student life information
- NUS Admissions requirements

## Trigger Phrases
- "what are the requirements for PhD in Computer Science"
- "tell me about NUS Master programs"
- "what modules are available for CS"
- "how do I apply to NUS"
- "what career services does NUS offer"

## Instructions
1. Receive the user's question
2. Perform hybrid retrieval (ChromaDB + BM25)
3. Apply Reciprocal Rank Fusion to merge results
4. Build context from top-5 retrieved chunks
5. Stream response via WaveSpeed AI
6. Append source URLs at the end

## Tools Used
- chroma_client: Vector similarity search
- bm25_search: Keyword-based search
- wavespeed_service: Streaming LLM response generation

## Output Format
Streaming text response with source citations at the end.

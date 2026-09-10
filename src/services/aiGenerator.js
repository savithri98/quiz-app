import { GoogleGenerativeAI } from "@google/generative-ai";

export async function generateQuestions(domain, difficulty, apiKey) {
    const genAI = new GoogleGenerativeAI(apiKey);
    const model = genAI.getGenerativeModel({ model: "gemini-2.5-flash" });

    const difficultyPrompt = difficulty === 'Mixed' ? 'a mix of Easy, Medium, and Hard' : `strictly ${difficulty}`;

    const prompt = `You are an expert exam setter. Generate exactly 10 distinct, unique Multiple Choice Questions for a competitive exam.
  
Domain/Topic: ${domain}
Difficulty: ${difficultyPrompt}

Requirements:
1. Output exactly 10 questions. No more, no less.
2. Each question must have exactly 4 options.
3. Indicate the correct option index (0 to 3).
4. Provide a detailed explanation for the correct answer. 
5. Your response MUST be valid JSON, conforming to the following structure exactly:

[
  {
    "question": "string",
    "options": ["string", "string", "string", "string"],
    "correctIndex": integer,
    "difficulty": "Easy" | "Medium" | "Hard",
    "explanation": "string (markdown allowed)"
  }
]
`;

    try {
        const result = await model.generateContent({
            contents: [{ role: 'user', parts: [{ text: prompt }] }],
            generationConfig: {
                responseMimeType: "application/json",
            }
        });

        const responseText = result.response.text();
        const cleanText = responseText.replace(/```json\\n?/gi, '').replace(/```\\n?/gi, '').trim();

        try {
            const data = JSON.parse(cleanText);
            if (!Array.isArray(data) || data.length === 0) {
                throw new Error("Invalid format received from AI.");
            }
            return data;
        } catch (parseError) {
            console.error("JSON Parse failed on:", cleanText);
            throw new Error("AI returned malformed or incomplete data. This often happens if the output is too long.");
        }

    } catch (err) {
        console.error("AI Generation Error: ", err);
        throw new Error(`Generation failed: ${err.message}`);
    }
}

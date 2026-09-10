import React, { useState } from 'react';
import { Settings, Play, BrainCircuit } from 'lucide-react';
import { generateQuestions } from '../services/aiGenerator';

export default function SetupScreen({ onComplete, setAppState }) {
    const [domain, setDomain] = useState('');
    const [difficulty, setDifficulty] = useState('Mixed');
    const [apiKey, setApiKey] = useState('');
    const [error, setError] = useState('');

    const handleGenerate = async (e) => {
        e.preventDefault();
        if (!domain.trim()) {
            setError('Please enter a domain or topic.');
            return;
        }
        if (!apiKey.trim()) {
            setError('Please provide your Gemini API key.');
            return;
        }

        setError('');
        setAppState('loading');

        try {
            const data = await generateQuestions(domain, difficulty, apiKey);
            if (data && data.length > 0) {
                onComplete(data);
            } else {
                throw new Error("No data returned from AI");
            }
        } catch (err) {
            console.error(err);
            setError(err.message || 'Failed to generate questions. Please check your API key and try again.');
            setAppState('setup');
        }
    };

    return (
        <div className="glass-panel animate-fade-in" style={{ maxWidth: '600px', margin: '0 auto' }}>
            <div className="flex flex-col items-center mb-6">
                <div style={{ background: 'var(--primary-glow)', padding: '1rem', borderRadius: '50%', marginBottom: '1rem' }}>
                    <BrainCircuit size={40} color="var(--primary)" />
                </div>
                <h2 style={{ fontSize: '1.8rem', fontWeight: '600' }}>Configure Your Practice</h2>
                <p style={{ color: 'var(--text-muted)' }}>Generate 50 unique questions instantly.</p>
            </div>

            <form onSubmit={handleGenerate} className="flex flex-col gap-4">
                <div>
                    <label className="label">Topic / Domain</label>
                    <input
                        type="text"
                        className="input-field"
                        placeholder="e.g. Quantum Physics, Indian History, AWS Cloud..."
                        value={domain}
                        onChange={(e) => setDomain(e.target.value)}
                    />
                </div>

                <div>
                    <label className="label">Difficulty</label>
                    <select
                        className="input-field"
                        value={difficulty}
                        onChange={(e) => setDifficulty(e.target.value)}
                    >
                        <option value="Mixed">Mixed (Easy, Medium, Hard)</option>
                        <option value="Easy">Easy</option>
                        <option value="Medium">Medium</option>
                        <option value="Hard">Hard</option>
                    </select>
                </div>

                <div>
                    <label className="label flex justify-between">
                        <span>Gemini API Key</span>
                        <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: 'var(--primary)', textDecoration: 'none' }}>Get Key</a>
                    </label>
                    <input
                        type="password"
                        className="input-field"
                        placeholder="AIzaSy..."
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                    />
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                        Your key is used only in your browser for this generation.
                    </p>
                </div>

                {error && (
                    <div style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)', borderRadius: '10px', color: 'var(--danger)' }}>
                        {error}
                    </div>
                )}

                <button type="submit" className="btn-primary mt-4" style={{ padding: '1rem' }}>
                    <Play size={20} /> Generate 50 MCQs
                </button>
            </form>
        </div>
    );
}

import React, { useState } from 'react';
import { ArrowRight, ArrowLeft, CheckCircle2 } from 'lucide-react';

export default function QuizScreen({ questions, onComplete, onQuit }) {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [answers, setAnswers] = useState({}); // { 0: 2, 1: 0, ... } mapping question index to selected option index

    const currentQ = questions[currentIndex];
    // Calculate total answered right now
    const answeredCount = Object.keys(answers).length;

    const handleOptionSelect = (optionIdx) => {
        setAnswers(prev => ({ ...prev, [currentIndex]: optionIdx }));
    };

    const handleNext = () => {
        if (currentIndex < questions.length - 1) {
            setCurrentIndex(curr => curr + 1);
        }
    };

    const handlePrev = () => {
        if (currentIndex > 0) {
            setCurrentIndex(curr => curr - 1);
        }
    };

    const handleFinish = () => {
        if (window.confirm('Are you ready to submit your answers?')) {
            onComplete(answers);
        }
    };

    return (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

            {/* Top Header / Progress */}
            <div className="glass-panel flex justify-between items-center" style={{ padding: '1rem 2rem' }}>
                <div>
                    <span style={{ fontSize: '1.2rem', fontWeight: 'bold' }}>Question {currentIndex + 1}</span>
                    <span style={{ color: 'var(--text-muted)' }}> / {questions.length}</span>
                    <span style={{ marginLeft: '1rem', padding: '0.2rem 0.6rem', background: 'var(--bg-elevated)', borderRadius: '20px', fontSize: '0.8rem', textTransform: 'uppercase', color: currentQ.difficulty === 'Hard' ? 'var(--danger)' : currentQ.difficulty === 'Medium' ? 'var(--primary)' : 'var(--accent)' }}>
                        {currentQ.difficulty}
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        Answered: {answeredCount} / {questions.length}
                    </div>
                    <button className="btn-secondary" style={{ padding: '0.5rem 1rem' }} onClick={onQuit}>Quit</button>
                </div>
            </div>

            {/* Progress Bar */}
            <div style={{ height: '4px', background: 'var(--bg-card)', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{ height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--secondary))', transition: 'width 0.3s ease', width: `${((currentIndex + 1) / questions.length) * 100}%` }}></div>
            </div>

            {/* Question Content */}
            <div className="glass-panel" style={{ padding: '3rem 2rem', minHeight: '300px' }}>
                <h2 style={{ fontSize: '1.5rem', lineHeight: '1.4', marginBottom: '2rem' }}>
                    {currentQ.question}
                </h2>

                <div className="flex flex-col gap-4">
                    {currentQ.options.map((opt, idx) => {
                        const isSelected = answers[currentIndex] === idx;
                        return (
                            <button
                                key={idx}
                                onClick={() => handleOptionSelect(idx)}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '1rem',
                                    padding: '1rem 1.5rem',
                                    background: isSelected ? 'var(--primary-glow)' : 'var(--bg-elevated)',
                                    border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border-color)'}`,
                                    borderRadius: '12px',
                                    color: 'var(--text-main)',
                                    fontSize: '1.1rem',
                                    cursor: 'pointer',
                                    transition: 'var(--transition-fast)',
                                    textAlign: 'left'
                                }}
                            >
                                <div style={{
                                    width: '28px', height: '28px',
                                    borderRadius: '50%',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    background: isSelected ? 'var(--primary)' : 'rgba(255,255,255,0.1)',
                                    fontWeight: 'bold', fontSize: '0.9rem'
                                }}>
                                    {String.fromCharCode(65 + idx)}
                                </div>
                                <span>{opt}</span>
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Navigation Footer */}
            <div className="flex justify-between items-center mt-4">
                <button
                    className="btn-secondary"
                    onClick={handlePrev}
                    disabled={currentIndex === 0}
                    style={{ opacity: currentIndex === 0 ? 0.5 : 1 }}
                >
                    <ArrowLeft size={18} /> Previous
                </button>

                {currentIndex === questions.length - 1 ? (
                    <button className="btn-primary" onClick={handleFinish}>
                        <CheckCircle2 size={18} /> Finish Quiz
                    </button>
                ) : (
                    <button className="btn-primary" onClick={handleNext}>
                        Next <ArrowRight size={18} />
                    </button>
                )}
            </div>

        </div>
    );
}

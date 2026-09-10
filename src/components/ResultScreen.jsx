import React from 'react';
import { Download, RotateCcw, CheckCircle2, XCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import html2pdf from 'html2pdf.js';

export default function ResultScreen({ questions, userAnswers, onRestart }) {
    let score = 0;
    questions.forEach((q, idx) => {
        if (userAnswers[idx] === q.correctIndex) score++;
    });

    const percentage = Math.round((score / questions.length) * 100);

    const handleDownload = () => {
        const element = document.getElementById('report-content');
        const opt = {
            margin: 0.5,
            filename: 'Exam_Prep_Report.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2 },
            jsPDF: { unit: 'in', format: 'letter', orientation: 'portrait' }
        };
        html2pdf().set(opt).from(element).save();
    };

    return (
        <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

            {/* Score Header */}
            <div className="glass-panel flex flex-col items-center justify-center" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
                <div style={{ position: 'relative', width: '150px', height: '150px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '50%', background: `conic-gradient(var(--primary) ${percentage}%, transparent 0)` }}>
                    <div style={{ position: 'absolute', inset: '8px', background: 'var(--bg-dark)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column' }}>
                        <span style={{ fontSize: '2.5rem', fontWeight: 'bold', lineHeight: '1' }}>{score}</span>
                        <span style={{ color: 'var(--text-muted)' }}>out of {questions.length}</span>
                    </div>
                </div>
                <h2 className="mt-6" style={{ fontSize: '2rem' }}>Practice Complete!</h2>
                <p style={{ color: 'var(--text-muted)' }}>Review your answers and explanations below.</p>

                <div className="flex gap-4 mt-6">
                    <button className="btn-secondary" onClick={onRestart}>
                        <RotateCcw size={18} /> New Test
                    </button>
                    <button className="btn-primary" onClick={handleDownload}>
                        <Download size={18} /> Download PDF
                    </button>
                </div>
            </div>

            {/* Review Section */}
            <div id="report-content" style={{ display: 'flex', flexDirection: 'column', gap: '2rem', background: 'var(--bg-dark)', padding: '1rem' }}>
                {/* PDF Header (only really visible/styled well in PDF or full screen) */}
                <div style={{ display: 'none' /* Will override via css in future if needed, keeping simple for now */ }}></div>

                {questions.map((q, qIndex) => {
                    const userAnswerIdx = userAnswers[qIndex];
                    const isCorrect = userAnswerIdx === q.correctIndex;

                    return (
                        <div key={qIndex} className="glass-panel" style={{ padding: '2rem' }}>
                            <div className="flex items-center gap-2 mb-4">
                                <span style={{ background: 'rgba(255,255,255,0.1)', padding: '0.2rem 0.8rem', borderRadius: '20px', fontSize: '0.9rem', fontWeight: 'bold' }}>
                                    Q{qIndex + 1}
                                </span>
                                {isCorrect ? (
                                    <span style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.9rem', fontWeight: 'bold' }}>
                                        <CheckCircle2 size={16} /> Correct
                                    </span>
                                ) : (
                                    <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.9rem', fontWeight: 'bold' }}>
                                        <XCircle size={16} /> Incorrect
                                    </span>
                                )}
                                <span style={{ marginLeft: 'auto', padding: '0.2rem 0.6rem', background: 'var(--bg-elevated)', borderRadius: '20px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                                    {q.difficulty}
                                </span>
                            </div>

                            <h3 style={{ fontSize: '1.2rem', marginBottom: '1.5rem', lineHeight: '1.4' }}>{q.question}</h3>

                            <div className="flex flex-col gap-3 mb-6">
                                {q.options.map((opt, oIndex) => {
                                    let bgCol = 'var(--bg-elevated)';
                                    let brCol = 'var(--border-color)';

                                    if (oIndex === q.correctIndex) {
                                        bgCol = 'rgba(16, 185, 129, 0.1)';
                                        brCol = 'var(--accent)';
                                    } else if (oIndex === userAnswerIdx && !isCorrect) {
                                        bgCol = 'rgba(239, 68, 68, 0.1)';
                                        brCol = 'var(--danger)';
                                    }

                                    return (
                                        <div key={oIndex} style={{ padding: '1rem', background: bgCol, border: `1px solid ${brCol}`, borderRadius: '8px', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                            <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem' }}>
                                                {String.fromCharCode(65 + oIndex)}
                                            </div>
                                            <span>{opt}</span>
                                        </div>
                                    );
                                })}
                            </div>

                            <div style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.3)', borderRadius: '12px', borderLeft: '4px solid var(--primary)' }}>
                                <h4 style={{ color: 'var(--primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    Explanation
                                </h4>
                                <div style={{ color: 'var(--text-muted)', lineHeight: '1.6', fontSize: '0.95rem' }} className="markdown-body">
                                    <ReactMarkdown>{q.explanation}</ReactMarkdown>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

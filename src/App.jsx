import React, { useState } from 'react';
import SetupScreen from './components/SetupScreen';
import QuizScreen from './components/QuizScreen';
import ResultScreen from './components/ResultScreen';

function App() {
  const [appState, setAppState] = useState('setup'); // 'setup', 'loading', 'quiz', 'results'
  const [quizData, setQuizData] = useState(null); // The generated 50 MCQs
  const [userAnswers, setUserAnswers] = useState({}); // Mapping from question index to chosen option index

  const handleStartQuiz = (data) => {
    setQuizData(data);
    setUserAnswers({});
    setAppState('quiz');
  };

  const handleCompleteQuiz = (answers) => {
    setUserAnswers(answers);
    setAppState('results');
  };

  const handleRestart = () => {
    setQuizData(null);
    setUserAnswers({});
    setAppState('setup');
  };

  return (
    <div className="container">
      <header className="header animate-fade-in">
        <h1>AI MCQ <span className="text-gradient">Generator</span></h1>
        <p>Master any domain with dynamic, AI-generated questions</p>
      </header>
      
      <main>
        {appState === 'setup' && (
          <SetupScreen onComplete={handleStartQuiz} setAppState={setAppState} />
        )}
        
        {appState === 'loading' && (
          <div className="glass-panel loading-container animate-fade-in">
            <div className="spinner"></div>
            <div className="loading-text">Generating your customized test...</div>
            <div className="loading-subtext">This might take up to a minute. We are crafting 50 unique questions.</div>
          </div>
        )}

        {appState === 'quiz' && quizData && (
          <QuizScreen 
            questions={quizData} 
            onComplete={handleCompleteQuiz} 
            onQuit={handleRestart} 
          />
        )}

        {appState === 'results' && quizData && (
          <ResultScreen 
            questions={quizData} 
            userAnswers={userAnswers} 
            onRestart={handleRestart} 
          />
        )}
      </main>
    </div>
  );
}

export default App;

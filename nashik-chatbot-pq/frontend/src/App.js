import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import "./App.css";
import LandingPage from "./components/LandingPage";
import ChatPage from "./components/ChatPage";
import PartLabeler from "./components/PartLabeler/PartLabeler";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/part-labeler" element={<PartLabeler />} />
      </Routes>
    </Router>
  );
}

export default App;

import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import "./App.css";
import LandingPage from "./components/LandingPage";
import ChatPage from "./components/ChatPage";
import PartLabeler from "./components/PartLabeler/PartLabeler";
import ZStage from "./components/ZStage/ZStage";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/part-labeler" element={<PartLabeler />} />
        <Route path="/z-stage" element={<ZStage />}/>
      </Routes>
    </Router>
  );
}

export default App;

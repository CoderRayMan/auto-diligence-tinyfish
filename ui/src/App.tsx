import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import AppBar from "./components/AppBar";
import Dashboard from "./pages/Dashboard";
import NewScan from "./pages/NewScan";

export default function App() {
  return (
    <BrowserRouter>
      <AppBar />
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/new-scan" element={<NewScan />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

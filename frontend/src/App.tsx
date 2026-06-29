import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import ImportCSV from "./pages/ImportCSV";
import TradesList from "./pages/TradesList";
import PLCalendar from "./pages/PLCalendar";
import Analysis from "./pages/Analysis";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/trades" replace />} />
        <Route path="/import" element={<ImportCSV />} />
        <Route path="/trades" element={<TradesList />} />
        <Route path="/calendar" element={<PLCalendar />} />
        <Route path="/analysis" element={<Analysis />} />
      </Route>
    </Routes>
  );
}

import type { ReactElement } from "react";
import CareerDashboard from "./CareerDashboard";
import TraineeList from "./TraineeList";

export const appMeta = {
  id: "careerforge",
  title: "CareerForge",
};

export const navSection = {
  title: "CareerForge",
  items: [
    { to: "/", label: "Dashboard" },
    { to: "/trainees", label: "Trainees" },
  ],
};

export interface AppRouteDef {
  path: string;
  element: ReactElement;
}

export const appRoutes: AppRouteDef[] = [
  { path: "/", element: <CareerDashboard /> },
  { path: "/trainees", element: <TraineeList /> },
];

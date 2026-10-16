import type { RouteObject } from "react-router-dom";
import { Layout } from "./components/Layout";
import { NotFound } from "./screens/NotFound";
import { Start } from "./screens/Start";

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Start /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

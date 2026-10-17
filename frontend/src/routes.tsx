import type { ReactNode } from "react";
import { Navigate, type RouteObject } from "react-router-dom";
import { Layout } from "./components/Layout";
import { GuestWorkspace, SavedWorkspace } from "./components/Workspace";
import type { Step } from "./store/importer";
import { Changes } from "./screens/Changes";
import { Facts } from "./screens/Facts";
import { NotFound } from "./screens/NotFound";
import { Plan } from "./screens/Plan";
import { Posts } from "./screens/Posts";
import { Privacy } from "./screens/Privacy";
import { Saved } from "./screens/Saved";
import { Start } from "./screens/Start";
import { Upcoming } from "./screens/Upcoming";

const SCREENS: Record<Step, () => ReactNode> = {
  facts: () => <Facts />,
  plan: () => <Plan />,
  posts: () => <Posts />,
  changes: () => <Changes />,
  upcoming: () => <Upcoming />,
};
const STEPS = Object.keys(SCREENS) as Step[];

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Start /> },
      { path: "/c/new", element: <Navigate to="/facts" replace /> },
      ...STEPS.map((step) => ({ path: `/${step}`, element: <GuestWorkspace step={step}>{SCREENS[step]()}</GuestWorkspace> })),
      { path: "/saved", element: <Saved /> },
      { path: "/privacy", element: <Privacy /> },
      { path: "/c/:id", element: <Navigate to="posts" replace /> },
      ...STEPS.map((step) => ({ path: `/c/:id/${step}`, element: <SavedWorkspace step={step}>{SCREENS[step]()}</SavedWorkspace> })),
      { path: "*", element: <NotFound /> },
    ],
  },
];

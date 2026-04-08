import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { Sidebar } from "@/components/layout/sidebar";
import { ImportPage } from "@/pages/import";
import { FifoPage } from "@/pages/fifo";
import { TransakcjePage } from "@/pages/transakcje";
import { SplityPage } from "@/pages/splity";
import { PortfolioPage } from "@/pages/portfolio";
import { DywidendyPage } from "@/pages/dywidendy";
import { KosztyPage } from "@/pages/koszty";
import { PodsumowaniePage } from "@/pages/podsumowanie";

// Root layout
const rootRoute = createRootRoute({
  component: () => (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  ),
});

// Routes
const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ImportPage,
});

const fifoRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/fifo",
  component: FifoPage,
});

const transakcjeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/transakcje",
  component: TransakcjePage,
});

const splityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/splity",
  component: SplityPage,
});

const portfolioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/portfolio",
  component: PortfolioPage,
});

const dywidendyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dywidendy",
  component: DywidendyPage,
});

const kosztyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/koszty",
  component: KosztyPage,
});

const podsumowanieRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/podsumowanie",
  component: PodsumowaniePage,
});

// Route tree
const routeTree = rootRoute.addChildren([
  indexRoute,
  fifoRoute,
  transakcjeRoute,
  splityRoute,
  portfolioRoute,
  dywidendyRoute,
  kosztyRoute,
  podsumowanieRoute,
]);

export const router = createRouter({ routeTree });

// Type safety
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

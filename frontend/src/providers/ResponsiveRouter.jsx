import { RouterProvider as ReactRouterProvider, createBrowserRouter } from 'react-router-dom';
import { useDevice } from '../hooks/useDevice';
import { createRouteConfig } from '../router';

export const ResponsiveRouter = () => {
  const isMobile = useDevice();
  const router = createBrowserRouter(createRouteConfig(isMobile));
  return <ReactRouterProvider router={router} />;
};

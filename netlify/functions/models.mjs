import {createApi} from '../lib/api.mjs';
const handle = createApi();
export default request => handle(request, 'models');
export const config = {
  path: '/api/models',
  method: 'GET',
  rateLimit: {windowSize: 60, windowLimit: 30, aggregateBy: ['domain']},
};

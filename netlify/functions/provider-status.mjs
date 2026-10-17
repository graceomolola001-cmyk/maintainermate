import {createApi} from '../lib/api.mjs';
const handle = createApi();
export default request => handle(request, 'provider-status');
export const config = {
  path: '/api/provider-status',
  method: 'GET',
  rateLimit: {windowSize: 60, windowLimit: 4, aggregateBy: ['domain']},
};

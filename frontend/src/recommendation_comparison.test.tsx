import { render, screen } from '@testing-library/react';
import { test, expect } from 'vitest';
import { RecommendationComparison } from './ResultComparison';
test('M and Q comparison shows exact saved fractions, without treating disabled as zero',()=>{
 const rate={value:50,numerator:2,denominator:4,status:'适用'};
 render(<RecommendationComparison data={{baseline:{set:'M',label:'推荐前：全部缺失场景',candidate_count:4,matched:2,metrics:{recommendation_adoption:rate,recommendation_false_positive:{value:100,numerator:2,denominator:2}}},recommended:{set:'Q',status:'未启用'}}}/>);
 expect(screen.getByText('50.00%（2/4）')).toBeTruthy();
 expect(screen.getAllByText('未启用').length).toBe(2);
 expect(screen.getByText(/同一选定GT版本/)).toBeTruthy();
});

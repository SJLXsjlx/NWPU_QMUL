%% 第三问
clear; clc; close all;

% 设置学术全局字体
set(groot, 'defaultAxesFontName', 'Cambria');
set(groot, 'defaultTextFontName', '华文中宋');

% 加载数据
excelPath = '附件：校园圈抽样数据.xlsx';

friendTable = readtable(excelPath, 'Sheet', '好友关系表');
userTable   = readtable(excelPath, 'Sheet', '用户属性表');
behavTable  = readtable(excelPath, 'Sheet', '行为数据表');

disp('Data loaded successfully');

% 绘图
G = graph(friendTable{:,1}, friendTable{:,2});

% Rename columns to English
userTable.Properties.VariableNames{1} = 'studentID';
userTable.Properties.VariableNames{2} = 'grade';
userTable.Properties.VariableNames{3} = 'majorCategory';
userTable.Properties.VariableNames{5} = 'clubs';

behavTable.Properties.VariableNames{1} = 'studentID';
behavTable.Properties.VariableNames{5} = 'techParticipation';
behavTable.Properties.VariableNames{3} = 'avgInteractFreq';
behavTable.Properties.VariableNames{7} = 'activePeriod';

disp(['Graph built: ' num2str(numnodes(G)) ' nodes, ' num2str(numedges(G)) ' edges']);

% 定义函数：传播概率模型
forwardProb = @(tech, freq, delay) (tech / 10) .* (freq / 25) .* exp(-delay / 24);

% 找到关键用户
degreeVec = degree(G);
techScore = behavTable.techParticipation;
interactFreq = behavTable.avgInteractFreq;

keyScore = degreeVec .* techScore .* interactFreq;
[~, sortedIdx] = sort(keyScore, 'descend');
topKeyUsers = string(G.Nodes.Name(sortedIdx(1:5)));  % Top 5 key users

disp(' ');
disp('=== Top 5 Key Users for Tech Topic Propagation ===');
for i = 1:5
    disp(['Key User #' num2str(i) ': ' char(topKeyUsers(i)) '   Score = ' num2str(keyScore(sortedIdx(i)))]);
end

% 模拟
seedUser = topKeyUsers(1); 
seedIdx = find(string(G.Nodes.Name) == seedUser);
nSim = 200; 
hours = 0:48;
reached = zeros(nSim, length(hours));

disp(['Simulating 48-hour propagation from ' char(seedUser) ' at 12:00...']);

for sim = 1:nSim
    active = false(numnodes(G), 1);
    active(seedIdx) = true;
    
    for t = 0:48
        newActive = false(numnodes(G), 1);
        currentActive = find(active);
        
        for u = currentActive'
            neigh = neighbors(G, u);
            for v = neigh'
                if ~active(v)
                    % Compute delay based on active period (simplified)
                    delay = mod(t, 24);  % Simple approximation
                    p = forwardProb(behavTable.techParticipation(v), ...
                                    behavTable.avgInteractFreq(v), delay);
                    if rand < p
                        newActive(v) = true;
                    end
                end
            end
        end
        active = active | newActive;
        reached(sim, t+1) = sum(active);
    end
end

meanReached = mean(reached, 1);
disp(['48-hour average reached users: ' num2str(meanReached(end))]);

% 可视化
figure('Position', [100 100 1000 600]);
plot(meanReached, 'LineWidth', 2);
xlabel('Hours after posting (12:00)');
ylabel('Average Reached Users');
title(['48-Hour Propagation Simulation from ' char(seedUser) ' (Tech Topic)']);
grid on;

disp(' ');
disp('Q3 simulation completed!');
disp('Right-click the figure window -> Save As to save the image.');
disp('The Top key user and simulation results are ready for the report.');
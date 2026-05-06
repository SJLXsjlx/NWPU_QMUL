%% 第四问
clear; clc; close all;

% 设置学术全局字体
set(groot, 'defaultAxesFontName', 'Cambria');
set(groot, 'defaultTextFontName', '华文中宋');

% 加载数据
excelPath = '附件：校园圈抽样数据.xlsx';

friendTable = readtable(excelPath, 'Sheet', '好友关系表', 'VariableNamingRule','preserve');
userTable   = readtable(excelPath, 'Sheet', '用户属性表', 'VariableNamingRule','preserve');
behavTable  = readtable(excelPath, 'Sheet', '行为数据表', 'VariableNamingRule','preserve');

disp('Data loaded successfully');

% 重命名
userTable.Properties.VariableNames{1} = 'studentID';
userTable.Properties.VariableNames{2} = 'grade';
userTable.Properties.VariableNames{3} = 'majorCategory';
userTable.Properties.VariableNames{5} = 'clubs';

behavTable.Properties.VariableNames{1} = 'studentID';
behavTable.Properties.VariableNames{2} = 'postCount';
behavTable.Properties.VariableNames{3} = 'avgInteractFreq';
behavTable.Properties.VariableNames{5} = 'techScore';
behavTable.Properties.VariableNames{6} = 'cultureScore';
behavTable.Properties.VariableNames{7} = 'activePeriod';

% 绘图
G = graph(friendTable{:,1}, friendTable{:,2});

% 概率计算
forwardProb = @(culture, freq, delay) (culture / 10) .* (freq / 25) .* exp(-delay / 24);

% 分数
degreeVec = degree(G);
influenceScore = degreeVec .* behavTable.cultureScore .* behavTable.avgInteractFreq;

% 优化
nPush = 10;
nSim = 100;

[~, sortedIdx] = sort(influenceScore, 'descend');
candidateSeeds = sortedIdx(1:50);

bestReach = 0;
bestSeeds = [];

for trial = 1:30
    seeds = candidateSeeds(randperm(length(candidateSeeds), nPush));
    reached = simulatePropagation(G, behavTable, seeds, nSim, forwardProb);
    finalReach = mean(reached(:, end));
    if finalReach > bestReach
        bestReach = finalReach;
        bestSeeds = seeds;
    end
end

disp(' ');
disp('=== Optimal 10-Push Strategy for Culture Topic ===');
disp(['Maximum 48-hour reach: ' num2str(bestReach) ' users']);
disp('Recommended seed users (first 5):');
disp(string(G.Nodes.Name(bestSeeds(1:5))));

% 模拟
function reached = simulatePropagation(G, behavTable, seeds, nSim, forwardProb)
    nNodes = numnodes(G);
    reached = zeros(nSim, 49);
    
    for sim = 1:nSim
        active = false(nNodes, 1);
        active(seeds) = true;
        
        for t = 0:48
            newActive = false(nNodes, 1);
            currentActive = find(active);
            
            for u = currentActive'
                neigh = neighbors(G, u);
                for v = neigh'
                    if ~active(v)
                        delay = mod(t, 24);
                        p = forwardProb(behavTable.cultureScore(v), ...
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
end

% 可视化
figure('Position', [100 100 800 500]);
plot(0:48, mean(reached,1), 'LineWidth', 2);
xlabel('Hours after first push');
ylabel('Average Reached Users');
title(['Culture Topic - Optimal 10-Push Strategy (Max Reach: ' num2str(bestReach) ')']);
grid on;

disp(' ');
disp('Q4 completed successfully!');
disp('Right-click figure to save image.');
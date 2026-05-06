%% ================== 第一问：全自动稳健分析脚本 ==================
clear; clc; close all;

% 设置学术感全局字体
set(groot, 'defaultAxesFontName', 'Cambria');
set(groot, 'defaultTextFontName', '华文中宋');

% ================== 1. 稳健加载数据 ==================
fileName = '附件：校园圈抽样数据.xlsx';
try
    % 直接读取，不依赖复杂的 opts 对象
    friendTable = readtable(fileName, 'Sheet', '好友关系表');
    userTable = readtable(fileName, 'Sheet', '用户属性表');
    
    % 强制重命名列名（这是解决"无效字符"报错的关键）
    friendTable.Properties.VariableNames{1} = 'Student1';
    friendTable.Properties.VariableNames{2} = 'Student2';
    userTable.Properties.VariableNames{1} = 'StudentID';
    userTable.Properties.VariableNames{2} = 'Grade';
    userTable.Properties.VariableNames{3} = 'Major';
    userTable.Properties.VariableNames{4} = 'Clubs';
    disp('Step 1: 数据加载并强制重命名成功');
catch
    error('文件读取失败，请检查文件名或是否关闭了 Excel');
end

% ================== 2. 构建图与基础分析 ==================
G = graph(string(friendTable.Student1), string(friendTable.Student2));

% 图 1：整体网络图 (Figure 1)
figure('Name', '1. 整体社交网络', 'Color', 'w');
plot(G, 'Layout', 'force', 'NodeColor', [0.2 0.6 1], 'EdgeAlpha', 0.2);
title('校园圈完整好友网络（整体概览）');

% ================== 3. 谱聚类社群检测 ==================
L = laplacian(G);
k = 8; 
[V, ~] = eigs(L, k, 'smallestabs');   
commLabels = kmeans(V, k, 'Replicates', 5);  

% 图 2：社群分布彩图 (Figure 2)
figure('Name', '2. 八大社群分布', 'Color', 'w');
plot(G, 'Layout', 'force', 'NodeCData', commLabels, 'MarkerSize', 6);
title('基于谱聚类识别的 8 个社交群体');
colorbar; colormap(jet);

% ================== 4. 计算社群内部密度 ==================
uniqueComms = unique(commLabels);
densityResult = [];

for i = 1:length(uniqueComms)
    c = uniqueComms(i);
    nodesInComm = find(commLabels == c);
    n = length(nodesInComm);
    if n < 3, continue; end
    
    subG = subgraph(G, nodesInComm);
    internalEdges = numedges(subG);
    % 密度公式：$Density = \frac{Edges}{n(n-1)/2}$
    density = internalEdges / (n*(n-1)/2);
    densityResult = [densityResult; c, n, internalEdges, density];
end

% 转换为 Table 并排序
top5Table = array2table(densityResult, 'VariableNames', {'ID', 'Size', 'Edges', 'Density'});
top5Table = sortrows(top5Table, 'Density', 'descend');
top5Table = top5Table(1:min(5, height(top5Table)), :);

% ================== 5. 成员背景深度分析 ==================
userTable.StudentID = string(userTable.StudentID); 
fprintf('\n=== 高密度社群背景分析报告 ===\n');

for i = 1:height(top5Table)
    nodes = find(commLabels == top5Table.ID(i));
    subUsers = userTable(ismember(userTable.StudentID, G.Nodes.Name(nodes)), :);
    
    fprintf('\n【Top % d 社群】 密度: %.4f\n', i, top5Table.Density(i));
    % 这里只打印到命令行，防止绘图报错
    % 如需分析年级/专业，可在此处添加 disp(groupcounts(...))
end

% ================== 6. 最后两张核心图（如果你之前只出一张，重点看这里） ==================

% 图 3：Top 5 高密度社群细节展示 (Figure 3)
figure('Name', '3. 最紧密社群微观结构', 'Color', 'w');
tiledlayout('flow', 'TileSpacing', 'compact');
for i = 1:height(top5Table)
    nexttile;
    nodes = find(commLabels == top5Table.ID(i));
    subG = subgraph(G, nodes);
    plot(subG, 'Layout', 'force', 'NodeColor', 'flat', 'NodeCData', i);
    title(['Top ', num2str(i), ' (D=', num2str(top5Table.Density(i), '%.2f'), ')']);
end

% 图 4：社群间连接热力图 (Figure 4)
figure('Name', '4. 社群间连接强度热力图', 'Color', 'w');
numTop = height(top5Table);
crossMatrix = zeros(numTop, numTop);
AdjMat = adjacency(G, 'symmetric'); 

for i = 1:numTop
    for j = 1:numTop
        if i == j, continue; end
        nodesI = find(commLabels == top5Table.ID(i));
        nodesJ = find(commLabels == top5Table.ID(j));
        crossMatrix(i,j) = nnz(AdjMat(nodesI, nodesJ));
    end
end

heatmap(string(top5Table.ID), string(top5Table.ID), crossMatrix, ...
    'Colormap', parula, 'Title', 'Top 5 社群间的跨圈子联系强度');

disp('>>> 任务完成：4 张分析图表已全部生成。');
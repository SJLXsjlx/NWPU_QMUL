%% 第一问
clear; clc; close all;

% 设置学术全局字体
set(groot, 'defaultAxesFontName', 'Cambria');
set(groot, 'defaultTextFontName', '华文中宋');

% 加载数据
excelPath = '附件：校园圈抽样数据.xlsx';
opts1 = detectImportOptions(excelPath, 'Sheet', '好友关系表');
friendTable = readtable(excelPath, opts1);

opts2 = detectImportOptions(excelPath, 'Sheet', '用户属性表');
userTable = readtable(excelPath, opts2);

% 重命名列名，避开中文索引报错
% 将好友表的第一列和第二列强制命名为 Student1, Student2
friendTable.Properties.VariableNames{1} = 'Student1';
friendTable.Properties.VariableNames{2} = 'Student2';

% 将用户表的第一列命名为 StudentID，后面几列按需命名
userTable.Properties.VariableNames{1} = 'StudentID';
userTable.Properties.VariableNames{2} = 'Grade';      % 年级
userTable.Properties.VariableNames{3} = 'Major';      % 专业类别
userTable.Properties.VariableNames{4} = 'Clubs';      % 所属社团

disp('数据加载并重命名成功！');

% 构建好友关系图
G = graph(string(friendTable.Student1), string(friendTable.Student2));  

disp(['网络规模：' num2str(numnodes(G)) ' 个学生']);

% 基础可视化
figure('Name', '整体好友网络');
plot(G, 'Layout', 'force', 'NodeColor', [0.2 0.6 1], 'EdgeAlpha', 0.3);
title('校园圈完整好友网络');

% 社区检测
L = laplacian(G);
k = 8; 
[V, ~] = eigs(L, k, 'smallestabs');   
commLabels = kmeans(V, k, 'Replicates', 5);  

% 计算社群密度
uniqueComms = unique(commLabels);
densityTable = table();

for i = 1:length(uniqueComms)
    c = uniqueComms(i);
    nodesInComm = find(commLabels == c);
    n = length(nodesInComm);
    if n < 3, continue; end
    
    subG = subgraph(G, nodesInComm);
    internalEdges = numedges(subG);
    maxPossible = n*(n-1)/2;
    density = internalEdges / maxPossible;
    
    densityTable = [densityTable; table(c, n, internalEdges, density, ...
        'VariableNames', {'ID', 'Size', 'Edges', 'Density'})];
end

densityTable = sortrows(densityTable, 'Density', 'descend');
top5 = densityTable(1:min(5, height(densityTable)), :); 

% 分析高密度社群成员分布
% 确保 ID 匹配用的列是字符串格式
userTable.StudentID = string(userTable.StudentID); 

for i = 1:height(top5)
    % 获取当前社群的所有成员ID
    nodes = find(commLabels == top5.ID(i));
    currentMemberIDs = G.Nodes.Name(nodes);
    
    % 在用户属性表中筛选这些成员
    subUsers = userTable(ismember(userTable.StudentID, currentMemberIDs), :);
    
    fprintf('\n【第 %d 个高密度社群】 规模=%d  密度=%.4f\n', i, top5.Size(i), top5.Density(i));
    
    % 年级和专业统计（这两个一般不会错）
    disp('年级分布：'); disp(groupcounts(subUsers, 'Grade'));
    disp('专业类别：'); disp(groupcounts(subUsers, 'Major'));
    
    % 统计社团
    disp('Top3社团：');
    % 1. 安全拆分社团字符串，全量过滤无效值
    tempClubs = join(subUsers.Clubs, ';');
    allClubs = split(tempClubs, ';');
    allClubs = strtrim(allClubs); % 去掉首尾空格
    allClubs = allClubs(~ismissing(allClubs) & allClubs ~= ""); % 彻底过滤空值
    
    % 空值保护：没有社团数据直接跳过
    if isempty(allClubs)
        disp('该社群暂无社团数据');
        continue;
    end
    
    % 手动统计频次
    [uniqueClubs, ~, idx] = unique(allClubs);
    countVals = accumarray(idx, 1); % 统计每个社团的出现次数
    
    % 手动降序排序
    [sortedCount, sortIdx] = sort(countVals, 'descend');
    sortedClubs = uniqueClubs(sortIdx);
    
    % 生成固定结构的结果表
    clubCounts = table(sortedClubs, sortedCount, 'VariableNames', {'社团名称', '出现次数'});
    
    % 显示Top3
    numToShow = min(3, height(clubCounts));
    disp(clubCounts(1:numToShow, :));
end

% 可视化Top5
figure('Name', 'Top社群展示');
tiledlayout('flow'); 
for i = 1:height(top5)
    nexttile;
    nodes = find(commLabels == top5.ID(i));
    subG = subgraph(G, nodes);
    plot(subG, 'Layout', 'force');
    title(['Top' num2str(i) ' Density=' num2str(top5.Density(i), '%.3f')]);
end

disp('运行完成！');